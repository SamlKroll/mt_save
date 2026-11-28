#!/usr/bin/env python3
"""Rebuild a sparse .uexp written by sparsify_uexp.py and verify its sha256.

    python3 tools/unsparsify.py --sparse assets/sparse.bin --out work/Jeju_World.uexp
"""
import argparse
import hashlib
import pathlib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sparse", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--meta", default=None)
    ap.add_argument("--expect-sha256", default=None)
    args = ap.parse_args()

    meta_path = pathlib.Path(args.meta or (args.sparse + ".meta"))
    meta = {}
    if meta_path.exists():
        for line in meta_path.read_text().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                meta[k] = v
        print(f"meta: {meta}")

    data = pathlib.Path(args.sparse).read_bytes()
    digest = hashlib.sha256(data).hexdigest()

    expect = args.expect_sha256 or meta.get("sparse_sha256")
    if expect and digest.lower() != expect.lower():
        raise SystemExit(f"transfer corrupt: sparse sha256 {digest} != {expect}")
    if expect:
        print("transfer OK — sparse payload arrived intact")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)

    kept = int(meta.get("kept", 0))
    zeros = len(data) - kept
    print(f"{out}: {len(data)} bytes ({kept} real, {zeros} zeroed)")
    print(f"windows kept: {meta.get('windows')}")
    print()
    print(f"original file sha256 was {meta.get('orig_sha256')}")
    print("this copy is enough for tools/patch_world.py --dry-run (it only reads the kept windows),")
    print("but it is NOT a drop-in replacement for the real .uexp — build the .pak from your full file.")


if __name__ == "__main__":
    main()
