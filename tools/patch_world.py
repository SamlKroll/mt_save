"""Patch AMTHouse.AreaSize (and MaxOutsidePlotDistance) of every placed house
inside a cooked Jeju_World.umap / Jeju_World.uexp pair.

Why this exists
---------------
In Motor Town the buildable border of a plot is the actor's own ``AreaSize``
(FVector, centimetres, doubles on UE5 with large world coordinates).  The save
file does not contain it and the DataTable only says which *class* a plot is, so
the only place the real numbers live is each AMTHouse instance inside the world
package.

The world package is split: ``Jeju_World.umap`` holds only the header (13.9 MB)
and every object's payload sits in ``Jeju_World.uexp`` (293 MB).  This tool reads
both, finds every export whose class is ``House_C`` / ``MTHouse``, decodes the
unversioned property stream using the schema from ``Mappings.usmap`` and rewrites
``AreaSize`` in place.  Nothing changes size, so offsets stay valid.

Usage
-----
    python3 tools/patch_world.py --umap Jeju_World.umap --uexp Jeju_World.uexp \
        --usmap Mappings.usmap --size 20000 --out patched/

    # only look, do not write:
    python3 tools/patch_world.py ... --dry-run
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import upak
import usmap


class Buf:
    """Little cursor over a bytearray; records where each property value starts."""

    def __init__(self, data: bytearray, pos: int = 0):
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

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]
        self.p += 8
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.d, self.p)[0]
        self.p += 4
        return v

    def f64(self):
        v = struct.unpack_from("<d", self.d, self.p)[0]
        self.p += 8
        return v

    def fstring(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            s = bytes(self.d[self.p:self.p - 2 * n]).decode("utf-16-le").rstrip("\x00")
            self.p += -2 * n
            return s
        s = bytes(self.d[self.p:self.p + n - 1]).decode("utf-8", "replace")
        self.p += n
        return s


def read_header(c: Buf):
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


class World:
    def __init__(self, umap_path, uexp_path):
        self.pkg = upak.Package(str(umap_path))
        self.data = bytearray(pathlib.Path(uexp_path).read_bytes())
        self.base = self.pkg.section_six  # uexp offset 0 == section six offset

    def payload(self, export):
        start = export["serial_offset"] - self.base
        return start, start + export["serial_size"]

    def iter_props(self, start, end, schema):
        """Yield (prop, value_offset, size) for every present property value."""
        c = Buf(self.data, start)
        present = read_header(c)
        for idx in present:
            prop = schema[idx]
            off = c.p
            skip_value(c, prop.type)
            yield prop, off, c.p - off
        if c.p > end:
            raise ValueError(f"overran export end {c.p} > {end}")


def skip_value(c: Buf, t):
    kind = t[0]
    if kind == "Bool":
        c.p += 1
    elif kind in ("Byte", "Int8"):
        c.p += 1
    elif kind in ("Int16", "UInt16"):
        c.p += 2
    elif kind in ("Int", "Int32", "UInt32", "Float", "Object", "Name", "Str"):
        c.p += 4
    elif kind in ("Int64", "UInt64", "Double"):
        c.p += 8
    elif kind == "Enum":
        skip_value(c, t[1])
    elif kind in ("Struct", "Array", "Map", "Set", "Text", "Optional"):
        raise ValueError(f"nested value of type {kind} needs schema walk ({t})")
    else:
        raise ValueError(f"unsupported type {t}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--umap", default="Jeju_World.umap")
    ap.add_argument("--uexp", default="Jeju_World.uexp")
    ap.add_argument("--usmap", default="Mappings.usmap")
    ap.add_argument("--size", type=float, default=20000.0, help="new plot side in cm (20000 = 200 m)")
    ap.add_argument("--height", type=float, default=5000.0)
    ap.add_argument("--outside", type=float, default=20000.0, help="MaxOutsidePlotDistance in cm")
    ap.add_argument("--out", default="patched", help="output directory")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    u = usmap.load(args.usmap)
    w = World(args.umap, args.uexp)
    pkg = w.pkg

    houses = [e for e in pkg.exports if pkg.export_class_name(e) in ("House_C", "MTHouse")]
    print(f"{len(houses)} house exports in {args.umap}")

    schema = u.all_props("MTHouse")
    owner_schema = schema
    owner_name = "MTHouse"
    area_idx = next(p.index for p in schema if p.name == "AreaSize")
    dist_idx = next(p.index for p in schema if p.name == "MaxOutsidePlotDistance")
    modified = 0

    for export in houses:
        start, end = w.payload(export)
        found = {}
        # A house may be the native MTHouse or the House_C blueprint; the latter
        # carries AreaSize too (blueprint properties come after the native ones).
        chain = []
        cls = pkg.export_class_name(export)
        if cls == "House_C":
            chain = [p for p in u.all_props("MTHouse")]
        try:
            props = list(w.iter_props(start, end, chain or schema))
        except Exception as exc:
            print(f"  {export['name'][:34]:<34} skipped: {exc}")
            continue
        for prop, off, size in props:
            if prop.name in ("AreaSize", "MaxOutsidePlotDistance"):
                found[prop.name] = (off, size)
        if "AreaSize" not in found:
            continue
        off, size = found["AreaSize"]
        assert size == 24, size  # 3 doubles
        cx, cy, cz = struct.unpack_from("<ddd", w.data, off)
        if not args.dry_run:
            struct.pack_into("<ddd", w.data, off, args.size, args.size, args.height)
            if "MaxOutsidePlotDistance" in found:
                doff, dsize = found["MaxOutsidePlotDistance"]
                if dsize == 4:
                    struct.pack_into("<f", w.data, doff, args.outside)
        print(f"  {export['name'][:34]:<34} ({cx:9.0f}, {cy:9.0f}, {cz:7.0f}) -> ({args.size:.0f}, {args.size:.0f}, {args.height:.0f})")
        modified += 1

    print(f"\n{modified} houses patched")
    if args.dry_run:
        return

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / pathlib.Path(args.umap).name).write_bytes(pkg.raw)
    (out / pathlib.Path(args.uexp).name).write_bytes(w.data)
    print(f"written to {out}/ — pack these two into BuildAnywhere_P.pak")


if __name__ == "__main__":
    main()
