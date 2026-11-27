"""Decode the /Game/DataAsset/Houses DataTable (MTHouseRow rows).

The table is what the housing market offers: name, price, whether the player may
build on it, and its plot size class (Small / Medium / Large).  Plot *dimensions*
live on the AMTHouse actor as AreaSize, so this table is the authoritative list of
which housingKeys are which size.
"""
import struct
import sys

sys.path.insert(0, "tools")
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
            s = self.d[self.p:self.p - 2 * n].decode("utf-16-le").rstrip("\x00")
            self.p += -2 * n
            return s
        s = self.d[self.p:self.p + n - 1].decode("utf-8", "replace")
        self.p += n
        return s


def read_header(c):
    """FUnversionedHeader -> (indices that carry values, zero-mask bits)."""
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
    mask_bits = []
    if zero_total:
        if zero_total <= 8:
            raw = c.u8()
            bits = [(raw >> i) & 1 for i in range(8)]
        elif zero_total <= 16:
            raw = c.u16()
            bits = [(raw >> i) & 1 for i in range(16)]
        else:
            words = (zero_total + 31) // 32
            raw = [c.u32() for _ in range(words)]
            bits = []
            for w in raw:
                bits.extend((w >> i) & 1 for i in range(32))
    else:
        bits = []

    present = []
    mi = 0
    for start, n, has_zero in frags:
        for k in range(n):
            if has_zero:
                is_zero = bits[mi]
                mi += 1
                if not is_zero:
                    present.append(start + k)
            else:
                present.append(start + k)
    return present, bits


def read_text(c):
    flags = c.u32()
    hist = c.s8()
    if hist == -1:  # None
        has = c.i32() == 1
        return c.fstring() if has else ""
    if hist == 0:  # Base
        c.fstring()  # namespace
        c.fstring()  # key
        return c.fstring()
    if hist == 11:  # StringTableEntry
        c.i32(); c.i32()  # table id FName
        return c.fstring()
    raise ValueError(f"text history {hist} at {c.p}")


def read_value(c, t, u):
    kind = t[0]
    if kind == "Text":
        return read_text(c)
    if kind == "Str":
        return c.fstring()
    if kind == "Object":
        return c.i32()
    if kind == "Name":
        i = c.i32(); c.i32()
        return ("name", i)
    if kind == "Int64":
        return c.i64()
    if kind == "Int32":
        return c.i32()
    if kind == "Int16":
        return struct.unpack_from("<h", c.d, c.p)[0] if not c.__dict__.update() else None
    if kind == "Bool":
        return c.u8() != 0
    if kind == "Float":
        return c.f32()
    if kind == "Double":
        return c.f64()
    if kind == "Enum":
        if t[1][0] == "Byte":
            return c.u8()
        raise ValueError(f"enum inner {t[1]}")
    if kind == "Array":
        n = c.i32()
        return [read_value(c, t[1], u) for _ in range(n)]
    if kind == "Struct":
        props = u.all_props(t[1])
        present, _ = read_header(c)
        return {props[i].name: read_value(c, props[i].type, u) for i in present}
    raise ValueError(f"unsupported type {t}")


def main():
    u = usmap.load("Mappings.usmap")
    pkg = upak.Package("Houses.uasset")
    exp = pkg.exports[0]
    data = open("Houses.uexp", "rb").read()
    c = Cur(data, exp["serial_offset"] - pkg.section_six)

    dt_schema = u.all_props("DataTable")
    present, _ = read_header(c)
    dt_props = {dt_schema[i].name: read_value(c, dt_schema[i].type, u) for i in present}
    row_struct_idx = dt_props["RowStruct"]
    name = pkg.imports[-row_struct_idx - 1]["object_name"] if row_struct_idx < 0 else str(row_struct_idx)
    print(f"DataTable row struct: {name}   (import key field: {dt_props.get('ImportKeyField')!r})")

    if c.i32() == 1:  # ObjectGuid
        c.p += 16

    n_rows = c.i32()
    schema = u.all_props(name)
    plot_names = {value: label for value, label in u.enums["EMTHousePlotSize"]}

    rows = {}
    for _ in range(n_rows):
        row_name = pkg.name(c.i32())
        c.i32()
        row, _ = read_value(c, ("Struct", name), u), None
        rows[row_name] = row

    print(f"\n{n_rows} rows, consumed {c.p}/{len(data)} bytes\n")
    print(f"{'housingKey':<24}{'plot':<8}{'cost':>10}  {'build':<6} title")
    print("-" * 78)
    for row_name, row in rows.items():
        plot = plot_names.get(row.get("PlotSize", 0), row.get("PlotSize", 0))
        title = row.get("Name", "")
        build = "yes" if row.get("bAllowBuilding") else "NO"
        print(f"{row_name:<24}{str(plot):<8}{row.get('Cost', 0):>10}  {build:<6} {title}")

    sizes = {}
    for row_name, row in rows.items():
        sizes.setdefault(plot_names.get(row.get("PlotSize", 0), row.get("PlotSize", 0)), []).append(row_name)
    print("\nby plot size:")
    for k in ("Small", "Medium", "Large"):
        print(f"  {k}: {len(sizes.get(k, []))} -> {', '.join(sizes.get(k, []))}")

    import json
    open("tools/houses_table.json", "w").write(json.dumps(rows, indent=2, ensure_ascii=False))
    print("\nwrote tools/houses_table.json")


if __name__ == "__main__":
    main()
