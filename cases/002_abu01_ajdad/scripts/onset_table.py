#!/usr/bin/env python3
"""10 ms table around a time window: RMS, f0, low-band share, flatness."""
import sys, json
import numpy as np, librosa, soundfile as sf

def table(path, a, b, label):
    y, sr = sf.read(path, always_2d=True); y = y.mean(1).astype(np.float32)
    hop = int(round(0.010 * sr))
    seg = y[int(a * sr):int(b * sr)]
    rms = librosa.feature.rms(y=seg, frame_length=2 * hop, hop_length=hop)[0]
    S = np.abs(librosa.stft(seg, n_fft=1024, hop_length=hop)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    lo = S[(f >= 100) & (f < 500)].sum(0); hi = S.sum(0) + 1e-15
    flat = librosa.feature.spectral_flatness(S=S)[0]
    f0 = librosa.pyin(y=seg, fmin=150, fmax=420, sr=sr, frame_length=2048,
                      hop_length=hop, fill_na=np.nan)[0]
    f0 = np.interp(np.arange(len(rms)), np.linspace(0, len(rms) - 1, len(f0)),
                   np.nan_to_num(f0, nan=0.0))
    ts = a + np.arange(len(rms)) * 0.010
    print(f"--- {label}  ({path.split('/')[-3]})  {a}-{b}")
    print("   t     rms    f0   lo%  flat")
    for i in range(len(rms)):
        if rms[i] < 1e-4 and f0[i] == 0:
            continue
        print(f"{ts[i]:7.3f} {rms[i]:6.4f} {f0[i]:5.0f} {100*lo[i]/hi[i]:5.0f} {flat[i]:5.4f}")

if __name__ == '__main__':
    table(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4] if len(sys.argv) > 4 else '')
