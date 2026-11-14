#!/usr/bin/env python3
"""Plot a word window with energy and gaps, for cut-point decisions.

Generic: works on any take that has a `words.json` in the aligner's format
(`{"words":[{"word","start","end"}...]}`) and a mix + vocal stem.

    python3 plot_gaps.py \
        --words words.json \
        --mix ORIGINAL.wav --vocals vocals.wav \
        --start 105.8 --end 113.6 \
        --span "B|109.10|111.35" \
        --line "A|108.88" --line "C|107.05" \
        --out gaps.html

Two rows: the full mix and the vocal stem. Word boxes come from the alignment;
low-energy regions are detected on the **vocal** (that is where the comp
happens). A gap in the mix is not a gap in the voice — the instruments fill it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np
import plotly.graph_objects as go
import soundfile as sf
from plotly.subplots import make_subplots


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def load_mono(path: Path) -> tuple[np.ndarray, int]:
    y, sr = sf.read(path, always_2d=True)
    return y.mean(1).astype(np.float32), sr


def envelope(y: np.ndarray, sr: int, a: float, b: float) -> tuple[np.ndarray, np.ndarray]:
    s, e = int(a * sr), int(b * sr)
    rms = librosa.feature.rms(y=y[s:e], frame_length=int(0.020 * sr),
                              hop_length=int(0.010 * sr), center=True)[0]
    t = a + np.arange(len(rms)) * 0.010
    return t, 20 * np.log10(rms + 1e-9)


def gaps(t: np.ndarray, db: np.ndarray, drop_db: float, min_s: float) -> list[tuple[float, float]]:
    thr = float(np.median(db)) - drop_db
    below = db < thr
    out: list[tuple[float, float]] = []
    i = 0
    while i < len(below):
        if not below[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(below) and below[j + 1]:
            j += 1
        if t[j] - t[i] >= min_s:
            out.append((float(t[i]), float(t[j])))
        i = j + 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", required=True)
    ap.add_argument("--mix", required=True)
    ap.add_argument("--vocals", required=True)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--span", action="append", default=[], help="name|start|end")
    ap.add_argument("--line", action="append", default=[], help="name|time")
    ap.add_argument("--out", required=True)
    ap.add_argument("--png", help="also write a PNG (needs kaleido)")
    ap.add_argument("--title", default="Word window — energy and gaps")
    ap.add_argument("--min-gap", type=float, default=0.040)
    ap.add_argument("--drop-db", type=float, default=8.0)
    args = ap.parse_args()

    a, b = args.start, args.end
    mix, sr_mix = load_mono(Path(args.mix).expanduser())
    voc, sr_voc = load_mono(Path(args.vocals).expanduser())
    tm, dbm = envelope(mix, sr_mix, a, b)
    tv, dbv = envelope(voc, sr_voc, a, b)
    words = [w for w in json.loads(Path(args.words).read_text())["words"]
             if w["end"] > a and w["start"] < b]

    def keep(gs):
        return [g for g in gs if g[0] > a + 0.01 and g[1] < b - 0.01]

    gv = keep(gaps(tv, dbv, args.drop_db, args.min_gap))
    gm = keep(gaps(tm, dbm, args.drop_db, args.min_gap))

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.10)

    for row, (t, db, name) in enumerate(((tm, dbm, "mix"), (tv, dbv, "vocal")), start=1):
        fig.add_trace(
            go.Scatter(x=t, y=db, mode="lines", name=name, showlegend=False,
                       line=dict(width=1.2),
                       customdata=[mmss(x) for x in t],
                       hovertemplate="%{customdata}<br>%{y:.1f} dB<extra>" + name + "</extra>"),
            row=row, col=1)
        fig.add_hline(y=float(np.median(db)) - args.drop_db, row=row, col=1,
                      line=dict(color="rgba(120,120,120,0.6)", dash="dot", width=1))
        # row label, in the free left margin of the row
        fig.add_annotation(x=a + 0.03, y=0.88, xref="x",
                           yref="y domain" if row == 1 else "y2 domain",
                           text=f"<b>{'المزيج' if row == 1 else 'الغناء'}</b> — "
                                f"{len(gm) if row == 1 else len(gv)} فجوة",
                           showarrow=False, xanchor="left",
                           font=dict(size=11, color="#4a5568"))

    # low-energy regions on the vocal, numbered
    for i, (g0, g1) in enumerate(gv, start=1):
        fig.add_vrect(x0=g0, x1=g1, row=2, col=1, fillcolor="rgba(40,160,90,0.30)",
                      line_width=0, layer="below")
        fig.add_annotation(x=(g0 + g1) / 2, y=0.855, yref="y2 domain", xref="x",
                           text=f"<b>{i}</b> · {mmss(g0)} · {1000*(g1-g0):.0f}ms",
                           showarrow=False, font=dict(size=8, color="white"),
                           bgcolor="#2f855a", borderpad=2)

    palette = ["#2b6cb0", "#805ad5", "#c05621", "#2f855a"]
    for k, spec in enumerate(args.span):
        name, s, e = spec.split("|")
        s, e = float(s), float(e)
        color = palette[k % len(palette)]
        fig.add_shape(type="rect", x0=s, x1=e, y0=0, y1=1, xref="x", yref="paper",
                      fillcolor=color, opacity=0.05, line_width=0)
        for x in (s, e):
            fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, xref="x", yref="paper",
                          line=dict(color=color, width=1.4, dash="dash"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                                 line=dict(color=color, width=2, dash="dash"),
                                 name=f"{name}  {mmss(s)} – {mmss(e)}"), row=1, col=1)
    for k, spec in enumerate(args.line):
        name, x = spec.split("|")
        x = float(x)
        color = palette[(k + len(args.span)) % len(palette)]
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, xref="x", yref="paper",
                      line=dict(color=color, width=1.2, dash="dot"))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines",
                                 line=dict(color=color, width=2, dash="dot"),
                                 name=f"{name}  {mmss(x)}"), row=1, col=1)

    # word boxes on both rows
    for w in words:
        for yref in ("y domain", "y2 domain"):
            fig.add_shape(type="rect", x0=w["start"], x1=w["end"], y0=0.93, y1=1.0,
                          xref="x", yref=yref, fillcolor="rgba(49,130,206,0.16)",
                          line=dict(color="rgba(49,130,206,0.55)", width=1))
            fig.add_annotation(x=(w["start"] + w["end"]) / 2, y=0.965, xref="x", yref=yref,
                               text=w["word"], showarrow=False,
                               font=dict(size=10, color="#1a365d"))

    fig.add_annotation(x=0.0, y=-0.19, xref="paper", yref="paper", showarrow=False,
                       align="left", font=dict(size=10, color="#718096"),
                       text=("الفجوة تُقاس على مسار الغناء (حيث يحدث اللصق)، لا على المزيج. "
                             "المربعات = حدود الكلمات من المحاذاة، وليست حدود القصّ."))

    tick0 = np.arange(np.floor(a * 2) / 2, b + 0.01, 0.5)
    fig.update_xaxes(tickmode="array", tickvals=tick0, ticktext=[mmss(x) for x in tick0],
                     tickangle=-45, row=2, col=1)
    fig.update_xaxes(range=[a, b])
    fig.update_yaxes(title_text="dB", range=[-50, -6], row=1, col=1)
    fig.update_yaxes(title_text="dB", range=[-50, -6], row=2, col=1)
    fig.update_layout(height=760, width=1500, title=args.title,
                      margin=dict(l=60, r=20, t=110, b=130),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="left", x=0, font=dict(size=10),
                                  bgcolor="rgba(255,255,255,0.9)"),
                      hovermode="x unified",
                      plot_bgcolor="white", paper_bgcolor="white")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out, include_plotlyjs=True, full_html=True)
    print(f"wrote {out}  ({out.stat().st_size/1e6:.1f} MB)")
    if args.png:
        fig.write_image(args.png, width=1600, height=900, scale=1)
        print(f"wrote {args.png}")
    print(f"vocal gaps: {[(round(x,3), round(y,3), round(1000*(y-x))) for x,y in gv]}")
    print(f"mix gaps:   {[(round(x,3), round(y,3), round(1000*(y-x))) for x,y in gm]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
