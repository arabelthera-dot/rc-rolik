"""Озвучка дня: days/<id>.json -> public/days/<id>/voice.mp3 + timeline.json; слова с временами — voice.words.json, voice.srt, voice.vtt."""
import asyncio, json, sys, re, subprocess, pathlib, random, time, hashlib
import edge_tts

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAP = 0.35  # пауза между сегментами, с
LEAD = 0.15  # голос стартует почти сразу — хук в 1-й секунде
TRIES = 10  # служба голоса отказывает волнами по несколько минут — окно повторов ≈5,5 мин на сцену (r264)
BEZ_UDAR = 3  # из TRIES попыток — последние без знаков ударения U+0301: служба на них отдаёт NoAudioReceived (r685, как audiogid.py)
PUSTO = 3  # звук <1 КБ или <0,3 с — пустой; столько пустых подряд — ошибка с именем дня (п.68)

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

def pustoj(mp3, words):
    """Почему звук пустой (п.68): нет слов, файл <1 КБ или длительность <0,3 с; '' — звук есть."""
    if not mp3.exists() or mp3.stat().st_size < 1024: return f"файл {mp3.stat().st_size if mp3.exists() else 0} Б"
    if not words: return "нет слов"
    try: d = dur(mp3)
    except Exception: return "ffprobe не читает файл"
    return f"{d:.2f} с" if d < 0.3 else ""

def ts(x, sep):
    ms = int(round(x * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"

def slova(out, segs):
    """Слова с временами рядом с voice.mp3 (п.67): voice.words.json, voice.srt, voice.vtt — по слову на строку субтитров."""
    ws = [{"t": w["t"], "d": round(w["d"], 3), "w": w["w"]} for sg in segs for w in sg["words"]]
    (out / "voice.words.json").write_text(json.dumps(ws, ensure_ascii=False, indent=0))
    cue = lambda w, sep: f"{ts(w['t'], sep)} --> {ts(w['t'] + max(w['d'], 0.05), sep)}\n{w['w']}\n"
    (out / "voice.srt").write_text("\n".join(f"{k + 1}\n" + cue(w, ",") for k, w in enumerate(ws)))
    (out / "voice.vtt").write_text("WEBVTT\n\n" + "\n".join(cue(w, ".") for w in ws))

def main(day):
    cfg = json.loads((ROOT / "days" / f"{day}.json").read_text())
    out = ROOT / "public" / "days" / day
    out.mkdir(parents=True, exist_ok=True)
    t = LEAD
    segs, parts = [], []
    for i, s in enumerate(cfg["segments"]):
        mp3, meta = out / f"seg{i}.mp3", out / f"seg{i}.json"
        text = udar(s["say"])
        key = hashlib.sha1(json.dumps([text, cfg["voice"], cfg["rate"]], ensure_ascii=False).encode()).hexdigest()
        old = json.loads(meta.read_text()) if meta.exists() else {}
        if mp3.exists() and old.get("key") == key and not pustoj(mp3, old["words"]):  # сцена уже озвучена тем же текстом — при перезапуске не переозвучиваем (r264)
            words = old["words"]
            print(f"  {s['id']}: готова, не переозвучиваю", flush=True)
        else:
            meta.unlink(missing_ok=True)
            pusto = 0
            for k in range(TRIES):  # повтор с растущей паузой 3, 6, 12, 24, 48, 60… с (r260, r264)
                bez = k >= TRIES - BEZ_UDAR or pusto > 0  # после пустого ответа — без знаков ударения
                try:
                    words = asyncio.run(synth(s["say"] if bez else text, cfg["voice"], cfg["rate"], mp3))
                    why = pustoj(mp3, words)
                    if not why: break
                    pusto += 1
                    if pusto >= PUSTO:
                        sys.exit(f"{day}: сцена {s['id']} — голос пустой {PUSTO} раза подряд ({why}), озвучка дня остановлена")
                    e = RuntimeError(why)
                except Exception as e1:
                    e = e1
                    if k == TRIES - 1:
                        sys.exit(f"{day}: сцена {s['id']} — голос не получен за {TRIES} попыток: {type(e).__name__} {e}")
                p = min(3 * 2 ** k, 60) + random.uniform(0, 3)
                print(f"  {s['id']}: попытка {k + 1} из {TRIES} — {type(e).__name__} {e}, жду {p:.0f} с", flush=True)
                time.sleep(p)
            if bez: print(f"  {s['id']}: озвучена БЕЗ знаков ударения", flush=True)
            meta.write_text(json.dumps({"key": key, "words": words, "bez_udarenij": bez}, ensure_ascii=False))
        d = dur(mp3)
        # подписи: если задан "show" — показываем его слова, разложив по времени озвученных слов
        show = s.get("show")
        if show:
            sw = re.split(r"[ \t\n]+", show.strip())  # неразрывный пробел (U+00A0) склеивает слова в подписи: «№ 17», «а в»
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
    slova(out, segs)
    (out / "day.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1))
    (out / "timeline.json").write_text(json.dumps({"total": round(total, 3), "segments": segs}, ensure_ascii=False, indent=1))
    print(f"{day}: {total:.1f} с, сегментов {len(segs)}")
    for s in segs:
        print(f"  {s['id']:8s} {s['start']:5.2f} +{s['dur']:.2f}")

if __name__ == "__main__":
    main(sys.argv[1])
