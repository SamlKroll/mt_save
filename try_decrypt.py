#!/usr/bin/env python3
"""
Attempt to decrypt MotorTown Island.world
- File in repo is UNCHANGED (sha256 matches HEAD), so this runs on original file.
- Tries: plain GVAS check, XOR repeating-key (known-plaintext GVAS), AES ECB/CBC
  with dictionary keys derived from plausible passwords, autocorrelation for XOR key length.
"""
import pathlib, hashlib, math, re, struct
from collections import Counter

path = pathlib.Path("Island.world")
data = path.read_bytes()
print(f"file: {path} size={len(data)} sha256={hashlib.sha256(data).hexdigest()}")
print(f"head hex: {data[:64].hex()}")
print(f"tail hex: {data[-64:].hex()}")
print(f"size % 16 = {len(data)%16}")

# entropy
c = Counter(data)
ent = -sum((v/len(data))*math.log2(v/len(data)) for v in c.values())
print(f"entropy bits/byte: {ent:.4f} (8.0 = random/encrypted/compressed)")

def printable_ratio(b):
    return sum(1 for x in b if 32 <= x < 127 or x in (10,13,9)) / max(1,len(b))

def count_strings(b, minlen=6):
    return re.findall(rb'[ -~]{%d,}' % minlen, b)

print("\n=== 1. Plain GVAS / zlib / zip check ===")
print("starts with GVAS?", data[:4]==b'GVAS')
print("starts with zlib 78 9c/da?", data[:2] in (b'\x78\x9c', b'\x78\xda', b'\x78\x01'))
print("starts with PK zip?", data[:2]==b'PK')
print("strings >=6 in raw:", len(count_strings(data)), count_strings(data)[:5])

print("\n=== 2. Block repeats (ECB indicator) ===")
blocks = [data[i:i+16] for i in range(0, len(data), 16)]
cnt = Counter(blocks)
print(f"total 16-byte blocks: {len(blocks)}, unique: {len(cnt)}")
for blk, n in cnt.most_common(5):
    print(f"  x{n}: {blk.hex()}")

print("\n=== 3. Autocorrelation for repeating-XOR key length ===")
# For each shift, fraction of equal bytes data[i]==data[i+shift]
# If XOR with repeating key length L and plaintext has repeats, shift=L spikes.
best = []
for shift in range(1, 513):
    # sample first 200k bytes for speed
    a = data[:200000]
    b = data[shift:200000+shift]
    eq = sum(1 for x,y in zip(a,b) if x==y) / len(a)
    best.append((eq, shift))
best.sort(reverse=True)
print("top shifts by byte-equality (random expect ~0.0039):")
for eq, s in best[:15]:
    print(f"  shift {s:4d}: {eq:.5f}")
# Also check shifts that are multiples of 16
print("shifts multiple of 16, top:")
for eq, s in [x for x in best if x[1]%16==0][:5]:
    print(f"  shift {s}: {eq:.5f}")

print("\n=== 4. Known-plaintext XOR attack (assume plaintext starts with 'GVAS') ===")
# If repeating XOR key K length L, K[0:4] = C[0:4] XOR 'GVAS'
gv = b'GVAS'
k0 = bytes(x ^ y for x,y in zip(data[:4], gv))
print(f"derived K[0:4] if XOR-repeating and plaintext=GVAS: {k0.hex()}  ({k0})")
# For each candidate L, we only know first 4 key bytes; test if decrypting with
# key repeated but unknown bytes treated as 0 gives any structure at positions 0, L, 2L...
# Better test: for shift = L, C[i] XOR C[i+L] should equal P[i] XOR P[i+L].
# If P has long zero runs, C[i]==C[i+L] in those runs. Autocorrelation above already tests this.
# Also try: assume most common plaintext block is zeros -> key = most common ciphertext block (tested before, failed)
most_common = cnt.most_common(1)[0][0]
dec = bytes(b ^ most_common[i%16] for i,b in enumerate(data[:8192]))
print(f"XOR with most-common-block as 16-byte key: printable={printable_ratio(dec):.3f}, strings={count_strings(dec)[:3]}")

print("\n=== 5. AES dictionary attack (ECB + CBC) ===")
try:
    from Crypto.Cipher import AES
    have_aes = True
except Exception as e:
    print("no AES lib:", e)
    have_aes = False

passwords = [
    "MotorTown","motortown","MOTORTOWN","Motor Town","MotorTownBehindTheWheel",
    "BehindTheWheel","behindthewheel","P3Games","P3","p3games","Island","island",
    "Jeju","jeju","MotorTown123","motortown123","1234567812345678","12345678",
    "password","secret","key","MotorTownSave","SaveGame","GVAS","Unreal",
    "UE5","MotorTown_Win64","MotorTown-Win64-Shipping",
]
def derive_keys(pw):
    b = pw.encode()
    out = {}
    out['md5'] = hashlib.md5(b).digest()          # 16
    out['sha256'] = hashlib.sha256(b).digest()    # 32
    out['sha1_16'] = hashlib.sha1(b).digest()[:16]
    out['raw16_pad0'] = (b + b'\x00'*16)[:16]
    out['raw32_pad0'] = (b + b'\x00'*32)[:32]
    out['raw16_repeat'] = (b * ((16//max(1,len(b)))+1))[:16]
    return out

def score_plain(pt):
    # GVAS magic is strongest signal, then printable ratio, then zlib
    s = 0
    if pt[:4]==b'GVAS': s += 100
    if pt[:2] in (b'\x78\x9c', b'\x78\xda', b'\x78\x01'): s += 20
    s += printable_ratio(pt[:4096]) * 10
    s += len(count_strings(pt[:8192], 8)) * 0.1
    return s

if have_aes:
    sample = data[:8192]  # decrypt sample for scoring, full decrypt only if hit
    hits = []
    tried = 0
    for pw in passwords:
        for kname, key in derive_keys(pw).items():
            for mode_name, mode in [('ECB', AES.MODE_ECB), ('CBC0', AES.MODE_CBC)]:
                try:
                    if mode_name=='ECB':
                        cipher = AES.new(key, AES.MODE_ECB)
                    else:
                        cipher = AES.new(key, AES.MODE_CBC, iv=b'\x00'*16)
                    pt = cipher.decrypt(sample[:len(sample)//16*16])
                    tried += 1
                    sc = score_plain(pt)
                    if sc > 5 or pt[:4]==b'GVAS':
                        hits.append((sc, pw, kname, mode_name, pt[:64]))
                        print(f"  HIT? score={sc:.2f} pw={pw!r} key={kname} mode={mode_name} head={pt[:64]}")
                except Exception:
                    pass
            # CBC with IV = first block, decrypt rest
            try:
                cipher = AES.new(key, AES.MODE_CBC, iv=data[:16])
                pt = cipher.decrypt(data[16:16+8192])
                tried += 1
                sc = score_plain(pt)
                if sc > 5 or pt[:4]==b'GVAS':
                    hits.append((sc, pw, kname, 'CBC_iv=first', pt[:64]))
                    print(f"  HIT? score={sc:.2f} pw={pw!r} key={kname} mode=CBC_iv=first head={pt[:64]}")
            except Exception:
                pass
    print(f"tried {tried} AES combos, hits={len(hits)}")
    if not hits:
        print("  -> no dictionary AES key produced GVAS / high printable. Key is not a simple password-derived key.")

print("\n=== 6. Other simple ciphers quick check ===")
# Single-byte XOR best printable
best_xor = []
for k in range(256):
    dec = bytes(b ^ k for b in data[:4096])
    best_xor.append((printable_ratio(dec), k))
best_xor.sort(reverse=True)
print(f"best single-byte XOR printable ratio: {best_xor[0]} (random ~0.37)")

print("\n=== Conclusion ===")
print("File is block-encrypted (ECB-like repeats, size%16==0, entropy~8).")
print("Without the key from MotorTown-Win64-Shipping.exe (reverse-engineered save key,")
print("NOT the pak AES key from AES Dumpster) decryption from the .world file alone is not feasible.")
print("motortowntools.com decrypts server-side with that key; no public decryptor was found.")
