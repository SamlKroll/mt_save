#!/usr/bin/env python3
"""Build a tiny .zip with just the house block of Jeju_World.uexp.

The sandbox cannot reach GitHub's release CDN (release-assets.githubusercontent.com
resets the TLS handshake), so a 145 MB release asset can't be pulled here.  But the
35 house actors sit in one 4 KB window of Jeju_World.uexp, and that is all the
patcher needs to validate decoding.

Run this on the machine that has the extracted game files:

    python3 tools/slice_uexp.py --uexp /path/to/Jeju_World.uexp \
        --start 242123897 --length 4222 --out houses_slice.zip

Then upload houses_slice.zip anywhere (message attachment is fine, it's ~2 KB).
"""
import argparse
import pathlib
import zipfile

DEFAULT_START = 242123897
DEFAULT_LENGTH = 4222


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uexp", required=True)
    ap.add_argument("--start", type=int, default=DEFAULT_START)
    ap.add_argument("--length", type=int, default=DEFAULT_LENGTH)
    ap.add_argument("--out", default="houses_slice.zip")
    args = ap.parse_args()

    src = pathlib.Path(args.uexp)
    size = src.stat().st_size
    print(f"{src}: {size} bytes")
    if size < args.start + args.length:
        raise SystemExit(f"file is shorter than the requested slice "
                         f"({args.start}+{args.length} > {size})")

    with open(src, "rb") as f:
        f.seek(args.start)
        data = f.read(args.length)

    out = pathlib.Path(args.out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"Jeju_World.uexp[{args.start}:{args.start + args.length}]", data)
    print(f"wrote {out} ({out.stat().st_size} bytes, {len(data)} payload bytes)")


if __name__ == "__main__":
    main()
