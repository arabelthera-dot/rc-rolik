"""Озвучка дня: days/<id>.json -> public/days/<id>/voice.mp3 + words.json (слова с таймингами)."""
import asyncio, json, sys, re, subprocess, pathlib, random, time
import edge_tts

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAP = 0.35  # пауза между сегментами, с
LEAD = 0.15  # голос стартует почти сразу — хук в 1-й секунде

async def synth(text, voice, rate, mp3):
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append({"t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7, "w": ch["text"].replace("\u0301", "")})
    return words

UDAR = {k: v for k, v in json.loads((ROOT / "udareniya.json").read_text()).items() if k != "_"}

def udar(text):
    """Ставит ударения из udareniya.json (регистр первой буквы сохраняется)."""
    def rep(m):
        w = m.group(0); v = UDAR.get(w.lower())
        if not v: return w
        return v[0].upper() + v[1:] if w[0].isupper() else v
    return re.sub(r"[А-Яа-яЁё]+", rep, text)

def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]))

def main(day):
    cfg = json.loads((ROOT / "days" / f"{day}.json").read_text())
    out = ROOT / "public" / "days" / day
    out.mkdir(parents=True, exist_ok=True)
    t = LEAD
    segs, parts = [], []
    for i, s in enumerate(cfg["segments"]):
        mp3 = out / f"seg{i}.mp3"
        for k in range(6):  # сервис голоса иногда рвёт связь — повтор с растущей паузой 3, 6, 12, 24, 48 с (r260)
            try:
                words = asyncio.run(synth(udar(s["say"]), cfg["voice"], cfg["rate"], mp3)); break
            except Exception as e:
                if k == 5: raise
                p = 3 * 2 ** k + random.uniform(0, 3)
                print(f"  {s['id']}: попытка {k + 1} из 6 — {type(e).__name__}, жду {p:.0f} с", flush=True)
                time.sleep(p)
        d = dur(mp3)
        # подписи: если задан "show" — показываем его слова, разложив по времени озвученных слов
        show = s.get("show")
        if show:
            sw = show.split()
            a, b = words[0]["t"], words[-1]["t"] + words[-1]["d"]
            n = len(sw)
            words = [{"t": a + (b - a) * k / n, "d": (b - a) / n, "w": w} for k, w in enumerate(sw)]
        else:
            # edge-tts отдаёт слова без пунктуации — возвращаем её из исходного текста
            src = s["say"].split()
            src = [w for w in src if re.search(r"\w", w)]
            if len(src) == len(words):
                for w, o in zip(words, src):  # подписи — из исходного текста, без знаков ударения
                    w["w"] = o
        segs.append({"id": s["id"], "start": t, "dur": d, "words": [{**w, "t": round(w["t"] + t, 3)} for w in words]})
        parts.append((mp3, t))
        t += d + GAP
    total = t + 0.6
    # склейка голоса в один файл с нужными смещениями
    args = ["ffmpeg", "-y", "-v", "error"]
    for p, _ in parts:
        args += ["-i", str(p)]
    fl = "".join(f"[{k}:a]adelay={int(o*1000)}|{int(o*1000)}[a{k}];" for k, (_, o) in enumerate(parts))
    fl += "".join(f"[a{k}]" for k in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0,apad,atrim=0:{total}[o]"
    args += ["-filter_complex", fl, "-map", "[o]", "-ar", "48000", "-c:a", "libmp3lame", "-b:a", "160k", str(out / "voice.mp3")]
    subprocess.check_call(args)
    (out / "day.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    (out / "timeline.json").write_text(json.dumps({"total": round(total, 3), "segments": segs}, ensure_ascii=False, indent=1))
    print(f"{day}: {total:.1f} с, сегментов {len(segs)}")
    for s in segs:
        print(f"  {s['id']:8s} {s['start']:5.2f} +{s['dur']:.2f}")

if __name__ == "__main__":
    main(sys.argv[1])
