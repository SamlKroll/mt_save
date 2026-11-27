"""Minimal .usmap reader that tolerates version 5 (UE 5.5 / Unreal 5.x).

Layout (same as pbzusmap / UAssetAPI, with name-length width by version):

    u8   magic low bytes 0xC4 0x30 already consumed
    u8   version
    if version >= 1 and next int32 > 0:   package versioning block
        int32 (ue4 version), int32 (ue5 version), uint32 custom count,
        custom count * (16 byte guid + int32), int32 net cl
    u8   compression method
    uint32 compressed size, uint32 decompressed size
    body:
        uint32 name count, then name count * (len (u16 if version>=2 else u8) + bytes)
        uint32 enum count
            each: uint32 name idx, u16 entry count, count * (int64 value if version>=4, uint32 name idx)
        uint32 schema count
            each: uint32 name idx, uint32 super idx (0xFFFFFFFF = none), u16, u16 prop count
                  each prop: u16 index, u8 array_dim, uint32 name idx, type
        optional extensions (CEXT/PPTH/EATR) ignored

types: 0 Byte, 1 Bool, 2 Int, 3 Float, 4 Object, 5 Name, 6 Delegate, 7 Double,
       8 Array, 9 Struct, 10 Str, 11 Text, 12 Interface, 13 MulticastDelegate,
       14 WeakObject, 15 LazyObject, 16 SoftObject, 17 UInt8, 18 UInt16, 19 UInt32,
       20 UInt64, 21 Int8, 22 Int16, 23 Int32, 24 Int64, 25 Map, 26 Set, 27 Enum,
       28 FieldPath, 29 Optional, 30 Utf8Str, 31 AnsiStr
"""
from __future__ import annotations

import struct
import zstandard

MAGIC = b"\xc4\x30"

TYPES = [
    "Byte", "Bool", "Int", "Float", "Object", "Name", "Delegate", "Double",
    "Array", "Struct", "Str", "Text", "Interface", "MulticastDelegate",
    "WeakObject", "LazyObject", "AssetObject", "SoftObject",
    "UInt64", "UInt32", "UInt16", "Int64", "Int16", "Int8",
    "Map", "Set", "Enum", "FieldPath", "Optional", "Utf8Str", "AnsiStr",
]
NO_NAME = 0xFFFFFFFF


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def take(self, fmt: str):
        v = struct.unpack_from("<" + fmt, self.data, self.pos)
        self.pos += struct.calcsize("<" + fmt)
        return v[0] if len(v) == 1 else v

    def bytes(self, n: int) -> bytes:
        b = self.data[self.pos:self.pos + n]
        self.pos += n
        return b

    def unpack(self, fmt: str):
        size = struct.calcsize("<" + fmt)
        v = struct.unpack_from("<" + fmt, self.data, self.pos)
        self.pos += size
        return v


class Prop:
    __slots__ = ("index", "array_dim", "name", "type")

    def __init__(self, index, array_dim, name, type_):
        self.index = index
        self.array_dim = array_dim
        self.name = name
        self.type = type_

    def type_text(self) -> str:
        return fmt_type(self.type)

    def __repr__(self):
        return f"{self.name}: {self.type_text()} idx={self.index}"


def fmt_type(t) -> str:
    kind = t[0]
    if kind in ("Array", "Set", "Optional"):
        return f"{kind}<{fmt_type(t[1])}>"
    if kind == "Map":
        return f"Map<{fmt_type(t[1])}, {fmt_type(t[2])}>"
    if kind == "Struct":
        return f"Struct<{t[1]}>"
    if kind == "Enum":
        return f"Enum<{t[2]}, {fmt_type(t[1])}>"
    return kind


class Struct:
    def __init__(self, name, super_name, props):
        self.name = name
        self.super = super_name
        self.props = props

    def __repr__(self):
        return f"Struct {self.name}(super={self.super}) with {len(self.props)} props"


class Usmap:
    def __init__(self, names, enums, structs, version):
        self.names = names
        self.enums = enums
        self.structs = structs
        self.version = version
        self.by_name = {s.name: s for s in structs}
        self.enum_by_name = dict(enums)
        self.name_to_index = {n: i for i, n in enumerate(names)}

    def get(self, name):
        return self.by_name.get(name)

    def all_props(self, name):
        """Walk the super chain and return props oldest-first (index order)."""
        chain = []
        cur = self.by_name.get(name)
        seen = set()
        while cur is not None and cur.name not in seen:
            seen.add(cur.name)
            chain.append(cur)
            cur = self.by_name.get(cur.super) if cur.super else None
        out = []
        for s in reversed(chain):
            out.extend(s.props)
        return out


def load(path: str) -> Usmap:
    raw = open(path, "rb").read()
    assert raw[:2] == MAGIC, f"bad usmap magic {raw[:2]!r}"
    r = Reader(raw, 2)
    version = r.take("B")

    if version >= 1:
        n = struct.unpack_from("<i", raw, r.pos)[0]
        if n > 0:
            r.take("ii")
            for _ in range(r.take("I")):
                r.bytes(20)
            r.take("i")

    if version >= 5:
        # v5 reorders the preamble (engine version block etc.); locate the frame directly.
        frame = raw.find(b"\x28\xb5\x2f\xfd")
        if frame < 0:
            raise ValueError("no zstd frame in usmap")
        compressed = struct.unpack_from("<I", raw, frame - 8)[0]
        decompressed = struct.unpack_from("<I", raw, frame - 4)[0]
        body = zstandard.ZstdDecompressor().decompress(raw[frame:], max_output_size=decompressed)
        assert len(body) == decompressed, (len(body), decompressed)
        assert frame + compressed == len(raw), (frame + compressed, len(raw))
    else:
        compression = r.take("B")
        compressed, decompressed = r.take("II")
        if compression == 0:
            body = r.bytes(compressed)
        elif compression == 3:  # ZStandard
            body = zstandard.ZstdDecompressor().decompress(r.bytes(compressed), max_output_size=decompressed)
        else:
            raise ValueError(f"unsupported compression method {compression}")
        assert len(body) == decompressed

    b = Reader(body)
    name_len = "H" if version >= 2 else "B"
    names = [b.bytes(b.take(name_len)).decode("utf-8", "replace") for _ in range(b.take("I"))]

    def name(may_be_none=False):
        i = b.take("I")
        if i == NO_NAME or i >= len(names):
            return None
        return names[i]

    def prop_type():
        kind = b.take("B")
        label = TYPES[kind] if kind < len(TYPES) else f"Unknown{kind}"
        if label in ("Array", "Set", "Optional"):
            return (label, prop_type())
        if label == "Map":
            key = prop_type()
            return ("Map", key, prop_type())
        if label == "Struct":
            return ("Struct", name())
        if label == "Enum":
            inner = prop_type()
            return ("Enum", inner, name())
        return (label,)

    enums = {}
    for _ in range(b.take("I")):
        enum_name = name()
        count = b.take("H") if version >= 3 else b.take("B")
        entries = []
        for i in range(count):
            value = b.take("q") if version >= 4 else i
            entries.append((value, name()))
        enums[enum_name] = entries

    structs = []
    for _ in range(b.take("I")):
        struct_name = name()
        super_name = name(may_be_none=True)
        b.take("H")
        props = []
        for _ in range(b.take("H")):
            index = b.take("H")
            array_dim = b.take("B")
            props.append(Prop(index, array_dim, name(), prop_type()))
        structs.append(Struct(struct_name, super_name, props))

    return Usmap(names, enums, structs, version)


if __name__ == "__main__":
    import sys
    u = load(sys.argv[1] if len(sys.argv) > 1 else "Mappings.usmap")
    print(f"version {u.version}: {len(u.names)} names, {len(u.enums)} enums, {len(u.structs)} structs")
    for want in sys.argv[2:]:
        s = u.get(want)
        print(s if s else f"{want}: not found")
