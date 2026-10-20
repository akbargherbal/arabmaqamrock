#!/usr/bin/env python3
"""Assemble the final S2 track: word-1 hybrid + phrase comp for the outro.

The base is the accepted e1 hybrid (`e1_ar_s03`), so word 1 stays fixed. The
outro phrase is replaced as one unit (default 202.21-207.90 s), either with the
candidate's full mix or with its vocal stem only (original instrumental kept).

Verifies that every changed sample lies inside the word-1 region and the S2
phrase region, and that the original WAV is unchanged.

Usage:
  python3 assemble_final_s2.py CANDIDATE.wav --stems DIR --seed s13 --out OUT.wav
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ORIG = os.path.join(REPO, "happy_accident/original/02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618.wav")
E1 = os.path.join(REPO, "happy_accident/runs/e1_resample/hybrid/e1_ar_s03.wav")
ORIG_STEMS = os.path.join(
    REPO,
    "happy_accident/runs/e2_phrase/stems/htdemucs/"
    "02-استيداع-قمر-بغداد-ولوعة-الوداع-B_1712905618",
)
E1_REGION = "156.995:158.855"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--stems", help="candidate Demucs dir (needed for vocal mode)")
    ap.add_argument("--mode", choices=["vocal", "full"], default="vocal")
    ap.add_argument("--seed", default="s13")
    ap.add_argument("--start", type=float, default=202.21)
    ap.add_argument("--end", type=float, default=207.90)
    ap.add_argument("--fade-in", type=float, default=0.05)
    ap.add_argument("--fade-out", type=float, default=0.12)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    cmd = [sys.executable, os.path.join(HERE, "comp_region.py"), E1, a.candidate, a.out,
           "--mode", a.mode, "--start", str(a.start), "--end", str(a.end),
           "--fade-in", str(a.fade_in), "--fade-out", str(a.fade_out), "--gain-ramp"]
    if a.mode == "vocal":
        if not a.stems:
            raise SystemExit("--stems is required for vocal mode")
        cmd += ["--orig-stems", ORIG_STEMS, "--cand-stems", a.stems]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    if r.returncode != 0:
        raise SystemExit(r.returncode)
    info = json.loads(r.stdout)

    v = subprocess.run(
        [sys.executable, os.path.join(HERE, "verify_final.py"), a.out, ORIG,
         E1_REGION, f"{a.start}:{a.end}"],
        capture_output=True, text=True)
    print(v.stdout.strip())
    if v.returncode != 0:
        raise SystemExit("final verification failed")
    print(json.dumps({"seed": a.seed, "mode": a.mode, "region_s": [a.start, a.end],
                      "out": a.out, **info}, indent=1))


if __name__ == "__main__":
    main()
