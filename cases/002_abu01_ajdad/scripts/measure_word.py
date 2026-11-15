#!/usr/bin/env python3
"""Measure the مِلَّتِي unit and the /m/ in a vocal stem.

Usage: measure.py <vocals.wav> <label> [--t0 OFFSET] [--full]
--t0    : time in the file (s) that corresponds to 0.0 s of the target timeline
          (i.e. the prefix length, if the file is tail-only). Default 0.
--full  : file covers the whole track; search the original word window.
Prints JSON. Does not decide anything; produces the numbers for the filter.
"""
import sys, json
import numpy as np
import librosa
import soundfile as sf


def band_rms(y, sr, n_fft=1024, hop=220, lo=180.0, hi=900.0):
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    m = (freqs >= lo) & (freqs <= hi)
    r = np.sqrt(S[m].mean(axis=0))
    return r, librosa.frames_to_time(np.arange(len(r)), sr=sr, hop_length=hop)


def main():
    path, label = sys.argv[1], sys.argv[2]
    t0 = 0.0
    full = '--full' in sys.argv
    if '--t0' in sys.argv:
        t0 = float(sys.argv[sys.argv.index('--t0') + 1])
    y, sr = sf.read(path, always_2d=True)
    y = y.mean(axis=1).astype(np.float32)
    dur = len(y) / sr

    out = {'label': label, 'path': path, 'sr': sr, 'duration': round(dur, 4), 't0': t0}

    # --- f0 (pyin) over the useful span ------------------------------------
    if full:
        a, b = 26.4 - t0, 31.2 - t0
    else:
        a, b = max(0.0, 26.4 - t0), min(dur, 31.2 - t0)
    seg = y[int(a * sr):int(b * sr)]
    if len(seg) < 2048:
        out['error'] = 'segment too short'
        print(json.dumps(out, indent=1)); return
    f0, vflag, vprob = librosa.pyin(seg, fmin=150, fmax=420, sr=sr,
                                    frame_length=2048, hop_length=220,
                                    fill_na=np.nan)
    tt = librosa.times_like(f0, sr=sr, hop_length=220) + a + t0
    voiced = ~np.isnan(f0)
    out['voiced_span'] = [round(float(tt[voiced][0]), 3), round(float(tt[voiced][-1]), 3)] if voiced.any() else None
    # coarse f0 track, 20 ms grid -> 20 points
    grid = np.arange(tt[0], tt[-1], 0.02)
    f0i = np.interp(grid, tt, np.nan_to_num(f0, nan=0.0))
    out['f0_track_20ms'] = [round(float(v), 0) for v in f0i[::10]]

    # --- low-band (nasal murmur) energy, 5 ms hop --------------------------
    r, rt = band_rms(seg, sr, hop=220)
    rt = rt + a + t0
    win = (rt >= 27.40) & (rt <= 27.75)
    if win.any():
        out['lowband_27.40_27.75'] = [round(float(rt[win][0]), 3), round(float(rt[win][-1]), 3)]
        out['lowband_peak_t'] = round(float(rt[win][np.argmax(r[win])]), 3)
        out['lowband_peak_v'] = round(float(r[win].max()), 6)

    # --- /m/ onset: 2 ms RMS + low-band murmur detector --------------------
    hop_f = 88  # 2 ms at 44.1k
    rms = librosa.feature.rms(y=seg, frame_length=512, hop_length=hop_f)[0]
    tr = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_f) + a + t0
    # spectral flatness: nasal murmur is tonal (low flatness); unvoiced /f/ is noisy
    flat = librosa.feature.spectral_flatness(y=seg, n_fft=1024, hop_length=hop_f)[0]
    tf = librosa.frames_to_time(np.arange(len(flat)), sr=sr, hop_length=hop_f) + a + t0
    sel = (tr >= 27.0) & (tr <= 28.1)
    out['rms_env_27.0_28.1'] = [[round(float(t), 3), round(float(v), 5)]
                                for t, v in zip(tr[sel][::5], rms[sel][::5])]
    sel2 = (tf >= 27.40) & (tf <= 27.70)
    out['flatness_27.40_27.70'] = [[round(float(t), 3), round(float(v), 4)]
                                   for t, v in zip(tf[sel2][::3], flat[sel2][::3])]

    # --- word end: last frame with f0 > 0 before 29.1, plus RMS drop ------
    m = (tt >= 27.9) & (tt <= 29.15) & voiced
    out['word_end_f0'] = round(float(tt[m][-1]), 3) if m.any() else None
    mr = (tr >= 28.4) & (tr <= 29.2)
    out['rms_28.4_29.2'] = [[round(float(t), 3), round(float(v), 5)]
                            for t, v in zip(tr[mr][::5], rms[mr][::5])]

    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
