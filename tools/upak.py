"""Parse unversioned (cooked) UE5 .uasset/.umap packages + .uexp, enough to read
data tables and tagged/unversioned property streams.

Header layout observed in Motor Town UE5.5 cooked assets (LegacyFileVersion = -8,
ObjectVersion/UE5 = 0 -> unversioned, custom version container empty):

   0  uint32  magic 0x9E2A83C1
   4  int32   legacy file version (-8)
   8  int32   legacy UE3 version (0)
  12  int32   UE4 version (0, unversioned)
  16  int32   UE5 version (0, unversioned)
  20  int32   licensee version
  24  int32   custom version count (0)
  28  int32   section six offset
  32  FString folder name
       uint32 package flags
       int32  name count
       int32  name offset
       int32  soft object paths count
       int32  soft object paths offset
       int32  gatherable text count
       int32  gatherable text offset
       int32  export count
       int32  export offset
       int32  import count
       int32  import offset
       int32  depends offset
       ... (unused here)
"""
from __future__ import annotations

import struct

from usmap import Usmap


class Name(str):
    pass


class Package:
    def __init__(self, uasset_path: str):
        self.raw = open(uasset_path, "rb").read()
        self.path = uasset_path
        d = self.raw
        magic, legacy = struct.unpack_from("<Ii", d, 0)
        assert magic == 0x9E2A83C1, hex(magic)
        self.legacy = legacy
        p = 8
        self.ue3, self.ue4, self.ue5, self.licensee = struct.unpack_from("<iiii", d, p)
        p += 16
        self.custom_count = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.section_six = struct.unpack_from("<i", d, p)[0]
        p += 4

        self.folder, p = self.read_fstring(p)
        self.package_flags = struct.unpack_from("<I", d, p)[0]
        p += 4
        self.name_count = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.name_offset = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.soft_path_count = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.soft_path_offset = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.gatherable_count = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.gatherable_offset = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.export_count = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.export_offset = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.import_count = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.import_offset = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.depends_offset = struct.unpack_from("<i", d, p)[0]
        p += 4
        self.header_end = p

        self.names = self.read_names()
        self.imports = self.read_imports()
        self.exports = self.read_exports()

    # ---------------------------------------------------------------- helpers
    def read_fstring(self, p):
        n = struct.unpack_from("<i", self.raw, p)[0]
        p += 4
        if n == 0:
            return "", p
        if n < 0:  # UTF-16
            s = self.raw[p:p + (-n) * 2].decode("utf-16-le").rstrip("\x00")
            return s, p + (-n) * 2
        s = self.raw[p:p + n].decode("utf-8", "replace").rstrip("\x00")
        return s, p + n

    def name(self, idx):
        if idx is None or idx < 0 or idx >= len(self.names):
            return None
        return self.names[idx]

    def read_names(self):
        d = self.raw
        p = self.name_offset
        out = []
        for _ in range(self.name_count):
            s, p = self.read_fstring(p)
            p += 4  # name hash
            out.append(s)
        self.names_end = p
        return out

    def read_imports(self):
        d = self.raw
        p = self.import_offset
        out = []
        for _ in range(self.import_count):
            cp_idx, _cpn, cn_idx, _cnn, outer, on_idx, _onn, extra = struct.unpack_from("<iiiiiiii", d, p)
            p += 32
            out.append(dict(
                class_package=self.name(cp_idx), class_name=self.name(cn_idx),
                outer=outer, object_name=self.name(on_idx), extra=extra))
        return out

    def read_exports(self):
        """Export map entry size is derived from the depends map offset."""
        d = self.raw
        p = self.export_offset
        self.export_entry_size = None
        if self.export_count > 0 and self.depends_offset > self.export_offset:
            span = self.depends_offset - self.export_offset
            if span % self.export_count == 0:
                self.export_entry_size = span // self.export_count
        out = []
        for i in range(self.export_count):
            cls, sup, tmpl, outer = struct.unpack_from("<iiii", d, p)
            on_idx, on_num = struct.unpack_from("<ii", d, p + 16)
            flags = struct.unpack_from("<I", d, p + 24)[0]
            size, offset = struct.unpack_from("<qq", d, p + 28)
            out.append(dict(index=i, class_index=cls, super_index=sup, template_index=tmpl,
                            outer=outer, name=self.name(on_idx), name_num=on_num,
                            flags=flags, serial_size=size, serial_offset=offset))
            p += (self.export_entry_size or 96)
        return out

    # ------------------------------------------------------------ class names
    def export_class_name(self, export):
        """Resolve the class of an export through the import table."""
        ci = export["class_index"]
        if ci < 0:
            imp = self.imports[-ci - 1]
            return imp["object_name"]
        if ci > 0:
            return self.exports[ci - 1]["name"]
        return None

    def export_super_name(self, export):
        si = export["super_index"]
        if si < 0:
            return self.imports[-si - 1]["object_name"]
        if si > 0:
            return self.exports[si - 1]["name"]
        return None
