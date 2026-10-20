#!/usr/bin/env python3
"""Verify a delivered track against the original.

Asserts that every changed sample lies inside the allowed regions, and prints
hashes, duration and the measured changed span.

Usage:
  python3 verify_final.py FINAL.wav ORIGINAL.wav [START:END ...]
"""
import hashlib
import sys

import numpy as np
import soundfile as sf


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main(final, original, *regions):
    y, sr = sf.read(final, dtype="int16", always_2d=True)
    o, sr2 = sf.read(original, dtype="int16", always_2d=True)
    assert sr == sr2 and y.shape == o.shape, (y.shape, o.shape, sr, sr2)
    d = np.abs(y.astype(np.int32) - o.astype(np.int32)).max(1)
    nz = np.where(d > 0)[0]
    runs = []
    if len(nz):
        s = p = nz[0]
        for i in nz[1:]:
            if i != p + 1:
                runs.append((s, p))
                s = i
            p = i
        runs.append((s, p))
    allowed = []
    for r in regions:
        a, b = r.split(":")
        allowed.append((float(a), float(b)))
    ok = True
    for a, b in runs:
        ta, tb = a / sr, (b + 1) / sr
        if not any(ta >= lo - 1e-3 and tb <= hi + 1e-3 for lo, hi in allowed):
            ok = False
            print(f"  OUTSIDE allowed region: {ta:.4f}-{tb:.4f}s")
    mask = np.ones(len(o), bool)
    for lo, hi in allowed:
        mask[int(round(lo * sr)):int(round(hi * sr))] = False
    outside = int(np.abs(y[mask].astype(np.int32) - o[mask].astype(np.int32)).max()) if mask.any() else 0
    print(f"file        {final}")
    print(f"original    {sha(original)}")
    print(f"final       {sha(final)}")
    print(f"format      {sr} Hz, {y.shape[1]} ch, {len(y)} frames, {len(y)/sr:.3f} s")
    print(f"changed runs {[(round(a/sr,4), round((b+1)/sr,4)) for a,b in runs]}")
    print(f"outside max abs diff vs original: {outside}")
    print("VERDICT:", "PASS" if ok and outside == 0 else "FAIL")
    return 0 if ok and outside == 0 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
