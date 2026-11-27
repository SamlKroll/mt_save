#!/usr/bin/env python3
"""Split a file into <100 MB parts so it can go through a GitHub release asset
or a plain git push (both fine; releases just cap at 2 GB per file).

    python3 tools/make_chunks.py --file /path/Jeju_World.uexp --outdir chunks --part-mb 95
"""
import argparse
import hashlib
import pathlib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--outdir", default="chunks")
    ap.add_argument("--part-mb", type=int, default=95)
    args = ap.parse_args()

    src = pathlib.Path(args.file)
    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    part = args.part_mb * 1024 * 1024
    total = src.stat().st_size
    print(f"{src}: {total} bytes -> {args.part_mb} MiB parts")

    with open(src, "rb") as f:
        i = 0
        while True:
            data = f.read(part)
            if not data:
                break
            p = out / f"{src.name}.part{i:02d}"
            p.write_bytes(data)
            print(f"  {p}  {len(data)} bytes  sha256={hashlib.sha256(data).hexdigest()[:16]}")
            i += 1
    print(f"{i} parts written to {out}/")


if __name__ == "__main__":
    main()
