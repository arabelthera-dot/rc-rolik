"""Звук без чужих записей: синтез numpy (гул-подложка, удар на хуке, «вжух» на смене сцен) + сведение с голосом.
Всё генерируется этим скриптом — лицензия CC0 (см. README). Выход: public/days/<id>/mix.mp3"""
import json, sys, subprocess, pathlib
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

ROOT = pathlib.Path(__file__).resolve().parent.parent
SR = 48000
rng = np.random.default_rng(5)

def env(n, a, r):
    e = np.ones(n); a = int(a * SR); r = int(r * SR)
    e[:a] = np.linspace(0, 1, a); e[-r:] *= np.linspace(1, 0, r); return e

def boom(d=1.6):
    t = np.arange(int(d * SR)) / SR
    f = 55 * np.exp(-t * 2.5) + 32  # падающий низкий тон
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    n = sosfilt(butter(2, 900, "low", fs=SR, output="sos"), rng.standard_normal(len(t))) * np.exp(-t * 18) * 0.6
    return (s + n) * 0.9

def whoosh(d=0.9):
    n = int(d * SR); x = rng.standard_normal(n)
    out = np.zeros(n); blk = 1024
    for i in range(0, n, blk):  # полоса фильтра едет вверх
        fc = 300 + 3500 * (i / n) ** 1.5
        out[i:i+blk] = sosfilt(butter(2, [fc * 0.6, fc * 1.4], "band", fs=SR, output="sos"), x[i:i+blk])
    t = np.linspace(0, 1, n)
    return out * np.sin(np.pi * t) ** 2 * 0.35

def drone(total):
    t = np.arange(int(total * SR)) / SR
    s = np.zeros_like(t)
    for f, a in [(55, 0.5), (82.4, 0.3), (110, 0.18), (164.8, 0.08)]:  # A–E, ровная «индустриальная» квинта
        s += a * np.sin(2 * np.pi * f * t + 0.3 * np.sin(2 * np.pi * 0.07 * t))
    hum = sosfilt(butter(2, [60, 400], "band", fs=SR, output="sos"), rng.standard_normal(len(t))) * 0.25
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
    return (s + hum) * lfo * env(len(t), 1.2, 2.0) * 0.16

def main(day):
    d = ROOT / "public" / "days" / day
    tl = json.loads((d / "timeline.json").read_text())
    total = tl["total"]
    mix = drone(total)
    def put(sig, at, g=1.0):
        i = int(at * SR); j = min(len(mix), i + len(sig)); mix[i:j] += sig[:j - i] * g
    put(boom(), 0.0, 0.8)
    for s in tl["segments"][1:]:
        put(whoosh(), max(0, s["start"] - 0.55), 0.8)
    put(boom(1.2), tl["segments"][-1]["start"] - 0.05, 0.45)
    mix = np.clip(mix, -1, 1)
    wavfile.write(d / "sfx.wav", SR, (mix * 32767).astype(np.int16))
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", str(d / "voice.mp3"), "-i", str(d / "sfx.wav"),
        "-filter_complex", "[1:a]volume=0.55[b];[0:a]volume=1.0[v];[v][b]amix=inputs=2:normalize=0,alimiter=limit=0.95,loudnorm=I=-15:TP=-1.5:LRA=11[o]",
        "-map", "[o]", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "160k", str(d / "mix.mp3")])
    print("mix.mp3 готов", total)

if __name__ == "__main__":
    main(sys.argv[1])
