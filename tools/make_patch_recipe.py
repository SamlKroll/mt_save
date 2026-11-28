#!/usr/bin/env python3
"""Turn the house window of Jeju_World.uexp into a tiny, verifiable patch recipe.

Needs only the 4 KB window that holds the 35 house actors (tools/slice_uexp.py
produces it), not the full 293 MB file: the patch overwrites 24 bytes per house
and never changes any length, so every offset stays valid.

Output: patch.json with one entry per house:

    {"offset": 242123961, "old": "<48 hex chars>", "new": "<48 hex chars>"}

The user applies it with tools/apply_patch_recipe.py, which refuses to touch
anything unless the bytes on disk still match "old".

    python3 tools/make_patch_recipe.py --window houses_slice.bin \
        --window-start 242123897 --umap Jeju_World.umap --usmap Mappings.usmap \
        --size 20000 --out patch.json
"""
import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import upak
import usmap


class Cur:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def s8(self):
        v = struct.unpack_from("<b", self.d, self.p)[0]
        self.p += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v


def read_header(c):
    frags = []
    first = 0
    while True:
        raw = c.u16()
        skip = raw & 0x7F
        has_zero = bool(raw & 0x80)
        value_num = (raw >> 9) & 0x7F
        is_last = bool(raw & 0x100)
        start = first + skip
        first = start + value_num
        frags.append((start, value_num, has_zero))
        if is_last:
            break
    zero_total = sum(n for _, n, hz in frags if hz)
    bits = []
    if zero_total:
        if zero_total <= 8:
            raw = c.u8()
            bits = [(raw >> i) & 1 for i in range(8)]
        elif zero_total <= 16:
            raw = c.u16()
            bits = [(raw >> i) & 1 for i in range(16)]
        else:
            for _ in range((zero_total + 31) // 32):
                w = c.u32()
                bits.extend((w >> i) & 1 for i in range(32))
    present = []
    mi = 0
    for start, n, has_zero in frags:
        for k in range(n):
            if has_zero:
                if not bits[mi]:
                    present.append(start + k)
                mi += 1
            else:
                present.append(start + k)
    return present


def value_size(t, schema_of, u):
    """Size of a serialized property value; supports the nested types Actors use."""
    kind = t[0]
    simple = {"Bool": 1, "Byte": 1, "Int8": 1, "Int16": 2, "UInt16": 2,
              "Int": 4, "Int32": 4, "UInt32": 4, "Float": 4, "Object": 4,
              "Name": 8, "Str": -1, "Int64": 8, "UInt64": 8, "Double": 8}
    if kind in simple:
        return simple[kind]
    raise ValueError(f"needs live cursor: {kind}")


PLAIN_STRUCTS = {"Vector", "Vector2D", "Vector4", "Rotator", "Quat", "Guid",
                 "LinearColor", "IntPoint", "IntVector", "Color", "Box",
                 "Plane", "Matrix", "Transform", "DateTime", "Timespan"}


def is_plain_struct(name):
    """Math/value structs are serialized without an unversioned property header."""
    return name in PLAIN_STRUCTS


def skip_value(c, t, u):
    """Advance the cursor over one property value. Returns its (offset, size)."""
    start = c.p
    kind = t[0]
    if kind in ("Bool", "Byte", "Int8"):
        c.p += 1
    elif kind in ("Int16", "UInt16"):
        c.p += 2
    elif kind in ("Int", "Int32", "UInt32", "Float", "Object"):
        c.p += 4
    elif kind == "Name":
        c.p += 8
    elif kind in ("Int64", "UInt64", "Double"):
        c.p += 8
    elif kind == "Str":
        n = c.i32()
        c.p += abs(n) * (2 if n < 0 else 1)
    elif kind == "Enum":
        skip_value(c, t[1], u)
    elif kind == "Struct":
        props = u.all_props(t[1]) if t[1] else []
        if is_plain_struct(t[1]):
            # Native math types (Vector, Guid, ...) have no unversioned header:
            # their components are written back to back.
            for p in props:
                skip_value(c, p.type, u)
            return start, c.p - start
        present = read_header(c)
        for idx in present:
            if idx >= len(props):
                raise ValueError(f"struct {t[1]} has only {len(props)} props, index {idx}")
            skip_value(c, props[idx].type, u)
    elif kind == "Array":
        n = c.i32()
        for _ in range(n):
            skip_value(c, t[1], u)
    elif kind == "Map":
        n = c.i32()
        for _ in range(n):
            skip_value(c, t[1], u)
            skip_value(c, t[2], u)
    elif kind == "Set":
        n = c.i32()
        for _ in range(n):
            skip_value(c, t[1], u)
    else:
        raise ValueError(f"unsupported type {t} at {start}")
    return start, c.p - start


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", required=True, help="houses_slice.bin from slice_uexp.py")
    ap.add_argument("--window-start", type=int, default=242123897,
                    help="file offset the window starts at")
    ap.add_argument("--umap", default="Jeju_World.umap")
    ap.add_argument("--usmap", default="Mappings.usmap")
    ap.add_argument("--size", type=float, default=20000.0, help="plot side in cm")
    ap.add_argument("--height", type=float, default=5000.0)
    ap.add_argument("--outside", type=float, default=20000.0,
                    help="MaxOutsidePlotDistance in cm; pass -1 to leave it alone")
    ap.add_argument("--out", default="patch.json")
    args = ap.parse_args()

    u = usmap.load(args.usmap)
    pkg = upak.Package(args.umap)
    data = pathlib.Path(args.window).read_bytes()
    wstart = args.window_start

    houses = [e for e in pkg.exports if pkg.export_class_name(e) in ("House_C", "MTHouse")]
    print(f"{len(houses)} house exports; window {wstart}..{wstart + len(data)}")

    patches = []
    skipped = []
    for export in houses:
        rel = export["serial_offset"] - pkg.section_six
        if not (wstart <= rel and rel + export["serial_size"] <= wstart + len(data)):
            skipped.append((export["name"], rel, "outside window"))
            continue
        base = rel - wstart
        c = Cur(data, base)
        try:
            present = read_header(c)
            props = u.all_props("MTHouse")
            area = dist = None
            for idx in present:
                prop = props[idx]
                off, size = skip_value(c, prop.type, u)
                if prop.name == "AreaSize":
                    area = (off, size)
                elif prop.name == "MaxOutsidePlotDistance":
                    dist = (off, size)
            if area is None:
                skipped.append((export["name"], rel, "no AreaSize"))
                continue
            aoff, asize = area
            if asize != 24:
                skipped.append((export["name"], rel, f"AreaSize is {asize} bytes, expected 24"))
                continue
            old = bytes(data[aoff:aoff + 24])
            new = struct.pack("<ddd", args.size, args.size, args.height)
            patches.append({"offset": wstart + aoff, "old": old.hex(), "new": new.hex(),
                            "house": export["name"], "old_cm": list(struct.unpack("<ddd", old))})
            if dist and args.outside >= 0:
                doff, dsize = dist
                if dsize == 4:
                    dold = bytes(data[doff:doff + 4])
                    dnew = struct.pack("<f", args.outside)
                    patches.append({"offset": wstart + doff, "old": dold.hex(), "new": dnew.hex(),
                                    "house": export["name"], "field": "MaxOutsidePlotDistance"})
        except Exception as exc:
            skipped.append((export["name"], rel, f"{type(exc).__name__}: {exc}"))

    doc = {
        "generated_for": pathlib.Path(args.umap).name,
        "uexp": "Jeju_World.uexp",
        "size_cm": args.size,
        "patches": patches,
    }
    pathlib.Path(args.out).write_text(json.dumps(doc, indent=1))
    print(f"\n{len(patches)} byte patches -> {args.out}")
    for p in patches[:40]:
        if p.get("field"):
            continue
        cx, cy, cz = p["old_cm"]
        print(f"  {p['offset']:>12}  {p['house'][:36]:<36} ({cx:8.0f}, {cy:8.0f}, {cz:6.0f})")
    if skipped:
        print(f"\n{len(skipped)} skipped:")
        for name, rel, why in skipped[:10]:
            print(f"  {name[:40]:<40} @{rel}  {why}")
    if not patches:
        raise SystemExit("no patches generated — check --window-start and the window file")


if __name__ == "__main__":
    main()
