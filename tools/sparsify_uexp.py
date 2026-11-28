#!/usr/bin/env python3
"""Turn a 293 MB Jeju_World.uexp into a ~10 MB sparse file that still lets the
patcher work: page-aligned windows of the original data, everything else zeroed.

    python3 tools/sparsify_uexp.py --uexp Jeju_World.uexp --window 242123897:4222 \
        --out sparse.bin

Windows can be repeated. Bytes outside the windows are written as zeros, so the
file keeps its exact size and every offset stays valid. tools/unsparsify.py
rebuilds the sparse copy on the other side and verifies the full sha256.
"""
import argparse
import hashlib
import pathlib
import struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uexp", required=True)
    ap.add_argument("--window", action="append", default=[],
                    help="start:length, repeatable (default: the 35-house window)")
    ap.add_argument("--page", type=int, default=4096, help="align windows to this many bytes")
    ap.add_argument("--out", default="sparse.bin")
    args = ap.parse_args()

    windows = args.window or ["242123897:4222"]
    src = pathlib.Path(args.uexp)
    size = src.stat().st_size
    print(f"{src}: {size} bytes")

    ranges = []
    for w in windows:
        a, b = w.split(":")
        start, length = int(a), int(b)
        page = args.page
        start = (start // page) * page
        end = ((start + length + page - 1) // page) * page
        if start >= size:
            print(f"  warning: window {w} starts past end of file ({start} >= {size}), skipped")
            continue
        ranges.append((start, min(size, end)))
    if not ranges:
        raise SystemExit("no usable windows: check --window values against the file size")
    ranges.sort()
    merged = []
    for s, e in ranges:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    h = hashlib.sha256()
    kept = 0
    with open(src, "rb") as f, open(args.out, "wb") as out:
        pos = 0
        for s, e in merged:
            while pos < s:
                chunk = f.read(min(1 << 20, s - pos))
                if not chunk:
                    break
                h.update(chunk)
                out.write(b"\x00" * len(chunk))
                pos += len(chunk)
            f.seek(s)
            data = f.read(e - s)
            h.update(data)
            out.write(data)
            kept += len(data)
            pos = e
            print(f"  keep {s}..{e}  ({len(data)} bytes)")
        while pos < size:
            chunk = f.read(min(1 << 20, size - pos))
            if not chunk:
                break
            h.update(chunk)
            out.write(b"\x00" * len(chunk))
            pos += len(chunk)

    orig_sha = h.hexdigest()
    sparse_sha = hashlib.sha256(pathlib.Path(args.out).read_bytes()).hexdigest()

    meta = pathlib.Path(args.out + ".meta")
    meta.write_text(
        f"name={pathlib.Path(args.uexp).name}\n"
        f"size={size}\n"
        f"orig_sha256={orig_sha}\n"
        f"sparse_sha256={sparse_sha}\n"
        f"kept={kept}\n"
        f"windows={','.join(f'{s}-{e}' for s, e in merged)}\n")

    out_size = pathlib.Path(args.out).stat().st_size
    print(f"\n{args.out}: {out_size} bytes (payload {kept})")
    print(f"{meta}:")
    print(f"  original sha256 = {orig_sha}   (check with: sha256sum Jeju_World.uexp)")
    print(f"  sparse   sha256 = {sparse_sha}   (checked after transfer)")
    print("push both files; tools/unsparsify.py rebuilds the original and verifies the hash")


if __name__ == "__main__":
    main()
