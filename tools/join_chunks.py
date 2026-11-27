#!/usr/bin/env python3
"""Reassemble parts written by make_chunks.py and verify the whole file.

    python3 tools/join_chunks.py --parts assets/chunks --out Jeju_World.uexp \
        --sha256 <expected>
"""
import argparse
import hashlib
import pathlib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True, help="directory with *.partNN files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sha256", default=None, help="expected sha256 of the joined file")
    args = ap.parse_args()

    d = pathlib.Path(args.parts)
    parts = sorted(d.glob("*.part*"))
    if not parts:
        raise SystemExit(f"no parts in {args.parts}")
    print(f"{len(parts)} parts")

    h = hashlib.sha256()
    total = 0
    out = pathlib.Path(args.out)
    with open(out, "wb") as w:
        for p in parts:
            data = p.read_bytes()
            w.write(data)
            h.update(data)
            total += len(data)
            print(f"  {p.name}  {len(data)}")
    digest = h.hexdigest()
    print(f"{out}: {total} bytes\nsha256={digest}")
    if args.sha256 and digest.lower() != args.sha256.lower():
        raise SystemExit("sha256 mismatch")
    if args.sha256:
        print("sha256 OK")


if __name__ == "__main__":
    main()
