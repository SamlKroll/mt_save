#!/usr/bin/env python3
"""Apply patch.json (from make_patch_recipe.py) to a real Jeju_World.uexp.

Every entry is verified before writing: if the bytes at the offset do not match
"old", the script stops instead of corrupting the file.

    python3 tools/apply_patch_recipe.py --uexp Jeju_World.uexp --recipe patch.json
"""
import argparse
import hashlib
import json
import pathlib
import shutil


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uexp", required=True)
    ap.add_argument("--recipe", default="patch.json")
    ap.add_argument("--out", default=None, help="write here instead of patching in place")
    ap.add_argument("--skip-sha", action="store_true")
    args = ap.parse_args()

    doc = json.loads(pathlib.Path(args.recipe).read_text())
    src = pathlib.Path(args.uexp)
    data = bytearray(src.read_bytes())
    print(f"{src}: {len(data)} bytes, {len(doc['patches'])} entries")

    if not args.skip_sha and doc.get("uexp_sha256"):
        digest = hashlib.sha256(data).hexdigest()
        if digest != doc["uexp_sha256"]:
            raise SystemExit(f"uexp sha256 {digest} does not match the recipe "
                             f"({doc['uexp_sha256']}) — wrong game version?")

    count = 0
    for entry in doc["patches"]:
        off = entry["offset"]
        old = bytes.fromhex(entry["old"])
        new = bytes.fromhex(entry["new"])
        have = bytes(data[off:off + len(old)])
        if have != old:
            raise SystemExit(
                f"offset {off} ({entry.get('house')}): expected {old.hex()}, found {have.hex()}. "
                "Nothing written.")
        data[off:off + len(new)] = new
        count += 1

    out = pathlib.Path(args.out or args.uexp)
    if out == src and not args.out:
        shutil.copy2(src, str(src) + ".bak")
        print(f"backup: {src}.bak")
    out.write_bytes(data)
    print(f"{count} patches applied -> {out}")
    print("now pack: repak pack --version V11 BuildAnywhere_P.pak MotorTown\\  (see BUILD_PAK.md)")


if __name__ == "__main__":
    main()
