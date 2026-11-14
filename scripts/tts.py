"""Озвучка дня: days/<id>.json -> public/days/<id>/voice.mp3 + timeline.json; слова с временами — voice.words.json, voice.srt, voice.vtt."""
import asyncio, json, sys, re, subprocess, pathlib, random, time, hashlib
import edge_tts
import zapasnoj_golos  # п.92: запасной Piper, выключен без ZAPASNOJ_GOLOS=piper

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAP = 0.35  # пауза между сегментами, с
LEAD = 0.15  # голос стартует почти сразу — хук в 1-й секунде
# Сцена без голоса не роняет ролик молча (Р765): 1) повтор с растущей паузой; 2) фраза делится по знакам на части,
# части озвучиваются отдельно и склеиваются; 3) весь день заново запасным голосом того же языка ZAPAS (голос не
# меняется посреди ролика); 4) Piper, если включён (п.92); иначе — выход с днём, сценой, голосом и ответом службы.
# Волна отказов NoAudioReceived у ru-RU-DmitryNeural длиннее прежнего окна 10 попыток ≈5,5 мин (r264, 13.11.2026:
# ns03feb f6, 04feb pyatno), а ru-RU-SvetlanaNeural в ту же минуту отвечала — окно сокращено, дальше части и запасной голос.
TRIES = 6  # повторы целой фразы: паузы 3, 6, 12, 24, 48 с ≈1,5 мин
BEZ_UDAR = 2  # из TRIES попыток — последние без знаков ударения U+0301: служба на них отдаёт NoAudioReceived (r685, как audiogid.py)
TRIES_CHAST = 3  # повторы одной части фразы
ZAPAS = {"ru-RU-DmitryNeural": "ru-RU-SvetlanaNeural", "ru-RU-SvetlanaNeural": "ru-RU-DmitryNeural"}  # тот же язык

class NetGolosa(Exception):
    """Служба не дала звук сцены ни целиком, ни по частям; в тексте — последний ответ службы."""

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

# Ударения: простые слова — udareniya.json здесь; имена и названия — один словарь сайта для всех роликов (п. 39),
# src/data/spravochniki/udareniya.json rc-site, в облаке его кладёт штатный checkout в rc-site-slovar/.
SLOVAR = ROOT / "rc-site-slovar" / "src" / "data" / "spravochniki" / "udareniya.json"
UDAR = {}

def udareniya():
    if not UDAR:
        if not SLOVAR.exists():
            raise SystemExit(f"нет словаря ударений сайта {SLOVAR} — в render.yml/audiogid.yml шаг checkout rc-site-slovar")
        UDAR.update({k: v for k, v in json.loads((ROOT / "udareniya.json").read_text()).items() if k != "_"})
        for k, z in json.loads(SLOVAR.read_text()).items():
            if k == "_": continue
            for f in z["formy"]:
                UDAR[f.replace("\u0301", "").lower()] = f.lower()
    return UDAR

def udar(text):
    """Ставит ударения из udareniya.json и словаря имён сайта (регистр первой буквы сохраняется)."""
    slova = udareniya()
    def rep(m):
        w = m.group(0); v = slova.get(w.lower())
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

def frazy(ws, dlina=42):
    """Слова сцены -> строки субтитров: фраза до точки, «?», «!», «…»; длинная делится на ровные строки до 42 знаков
    (норма строки субтитров) разбиением с наименьшим штрафом, как перенос строк у Кнута — Пласса: без хвоста в одно
    слово и без строки, начатой тире."""
    predl, cur = [], []
    for w in ws:
        cur.append(w)
        if re.search(r"[.!?…]$", w["w"]): predl.append(cur); cur = []
    if cur: predl.append(cur)
    out = []
    for p in predl:
        n = len(p); best = [0.0] + [float("inf")] * n; ot = [0] * (n + 1)
        for j in range(1, n + 1):
            for i in range(j - 1, -1, -1):
                L = len(" ".join(w["w"] for w in p[i:j]))
                if L > dlina and j - i > 1: break
                shtraf = (dlina - L) ** 2 + (400 if j - i == 1 and n > 1 else 0) + (400 if p[i]["w"] in "—–-" else 0)
                if best[i] + shtraf < best[j]: best[j], ot[j] = best[i] + shtraf, i
        kusky, j = [], n
        while j: kusky.append(p[ot[j]:j]); j = ot[j]
        out += kusky[::-1]
    return out

def slova(out, segs):
    """Слова с временами рядом с voice.mp3 (п.67): voice.words.json — по слову; voice.srt, voice.vtt — субтитры строками
    из текста сценария (show, иначе say, без знаков ударения) по времени озвученных слов (r725 п.131); voice.txt — текст
    ролика по сцене на строку, для расшифровки на странице дня (r725 п.138)."""
    chisto = lambda x: x.replace("\u0301", "").replace("\u00a0", " ")
    ws = [{"t": w["t"], "d": round(w["d"], 3), "w": chisto(w["w"])} for sg in segs for w in sg["words"]]
    (out / "voice.words.json").write_text(json.dumps(ws, ensure_ascii=False, indent=0))
    stroki = [f for sg in segs for f in frazy([{**w, "w": chisto(w["w"])} for w in sg["words"]])]
    cue = lambda f, sep: f"{ts(f[0]['t'], sep)} --> {ts(f[-1]['t'] + max(f[-1]['d'], 0.05), sep)}\n{' '.join(w['w'] for w in f)}\n"
    (out / "voice.srt").write_text("\n".join(f"{k + 1}\n" + cue(f, ",") for k, f in enumerate(stroki)))
    (out / "voice.vtt").write_text("WEBVTT\nKind: subtitles\nLanguage: ru\n\n" + "\n".join(cue(f, ".") for f in stroki))
    (out / "voice.txt").write_text("".join(" ".join(chisto(w["w"]) for w in sg["words"]) + "\n" for sg in segs))

def popytka(text, voice, rate, mp3):
    words = asyncio.run(synth(text, voice, rate, mp3))
    why = pustoj(mp3, words)
    if why: raise RuntimeError(f"пустой звук ({why})")
    return words

def pauza(k, imya, n, e):
    p = min(3 * 2 ** k, 60) + random.uniform(0, 3)
    print(f"  {imya}: попытка {k + 1} из {n} — {type(e).__name__} {e}, жду {p:.0f} с", flush=True)
    time.sleep(p)

def chasti(text):
    """Фраза -> части по знакам препинания (не короче 3 слов, чтобы не рвать интонацию на каждом слове)."""
    kusky = [k.strip() for k in re.split(r"(?<=[,.:;!?…—])\s+", text) if k.strip()]
    out = []
    for k in kusky:
        if out and len(out[-1].split()) < 3: out[-1] += " " + k
        else: out.append(k)
    return out

def ozvuchit_scenu(sid, text, bez_udar, voice, rate, mp3):
    """Шаги 1–2: повтор целой фразы, затем по частям. Возвращает (words, bez_udarenij) или NetGolosa."""
    e = None
    for k in range(TRIES):  # шаг 1: повтор с растущей паузой (r260, r264)
        bez = k >= TRIES - BEZ_UDAR or (e is not None and "пустой" in str(e))  # после пустого ответа — без знаков ударения
        try: return popytka(bez_udar if bez else text, voice, rate, mp3), bez
        except Exception as e1: e = e1
        if k < TRIES - 1: pauza(k, sid, TRIES, e)
    kusky = chasti(bez_udar)  # шаг 2: части без знаков ударения — на них служба отказывает чаще
    if len(kusky) < 2: raise NetGolosa(f"{type(e).__name__} {e}")
    print(f"  {sid}: целиком не озвучена — делю на {len(kusky)} части по знакам", flush=True)
    words, t, spisok = [], 0.0, mp3.with_suffix(".chasti.txt")
    for n, kus in enumerate(kusky):
        cm = mp3.with_name(f"{mp3.stem}.ch{n}.mp3")
        for k in range(TRIES_CHAST):
            try: ws = popytka(kus, voice, rate, cm); break
            except Exception as e1: e = e1
            if k == TRIES_CHAST - 1: raise NetGolosa(f"часть {n + 1} из {len(kusky)} «{kus}»: {type(e).__name__} {e}")
            pauza(k, f"{sid} часть {n + 1}", TRIES_CHAST, e)
        words += [{**w, "t": w["t"] + t} for w in ws]
        t += dur(cm)
    spisok.write_text("".join(f"file '{mp3.with_name(f'{mp3.stem}.ch{n}.mp3').name}'\n" for n in range(len(kusky))))
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(spisok), "-c", "copy", str(mp3)])
    for n in range(len(kusky)): mp3.with_name(f"{mp3.stem}.ch{n}.mp3").unlink(missing_ok=True)
    spisok.unlink()
    print(f"  {sid}: озвучена ПО ЧАСТЯМ ({len(kusky)})", flush=True)
    return words, True

def main(day, voice=None):
    cfg = json.loads((ROOT / "days" / f"{day}.json").read_text())
    osnovnoj = cfg["voice"]
    if voice: cfg["voice"] = voice
    out = ROOT / "public" / "days" / day
    out.mkdir(parents=True, exist_ok=True)
    t = LEAD
    segs, parts = [], []
    for i, s in enumerate(cfg["segments"]):
        mp3, meta = out / f"seg{i}.mp3", out / f"seg{i}.json"
        text = udar(s["say"])
        key = hashlib.sha1(json.dumps([text, cfg["voice"], cfg["rate"]], ensure_ascii=False).encode()).hexdigest()
        old = json.loads(meta.read_text()) if meta.exists() else {}
        if mp3.exists() and old.get("key") == key and not old.get("zapasnoj") and not pustoj(mp3, old["words"]):  # сцена уже озвучена тем же текстом — при перезапуске не переозвучиваем (r264)
            words = old["words"]
            print(f"  {s['id']}: готова, не переозвучиваю", flush=True)
        else:
            meta.unlink(missing_ok=True)
            zap = False
            try:
                words, bez = ozvuchit_scenu(s["id"], text, s["say"], cfg["voice"], cfg["rate"], mp3)
            except NetGolosa as e:
                zapas = ZAPAS.get(osnovnoj)
                if not voice and zapas:  # шаг 3: весь день запасным голосом того же языка
                    print(f"::warning::{day}: сцена {s['id']} — голос {osnovnoj} не получен ({e}); день целиком озвучивается голосом {zapas}", flush=True)
                    return main(day, zapas)
                if not zapasnoj_golos.vklyuchen():  # шаг 4 — Piper, иначе точная причина
                    golosa = osnovnoj + (f", затем {voice}" if voice else "")
                    sys.exit(f"{day}: сцена {s['id']} — голос не получен ({golosa}; повтор {TRIES} раз, по частям, запасной голос): ответ службы {e}")
                zap = True
            if zap:  # edge-tts не ответил — Piper; при следующем прогоне сцена снова пойдёт в edge-tts
                words = zapasnoj_golos.ozvuchit(text, cfg["rate"], mp3)
                if pustoj(mp3, words): sys.exit(f"{day}: сцена {s['id']} — и запасной голос пустой ({pustoj(mp3, words)})")
                print(f"  {s['id']}: озвучена ЗАПАСНЫМ голосом Piper {zapasnoj_golos.GOLOS}", flush=True)
                bez = False
            if bez: print(f"  {s['id']}: озвучена БЕЗ знаков ударения", flush=True)
            meta.write_text(json.dumps({"key": key, "words": words, "bez_udarenij": bez, **({"zapasnoj": zapasnoj_golos.GOLOS} if zap else {})}, ensure_ascii=False))
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
    print(f"{day}: {total:.1f} с, сегментов {len(segs)}, голос {cfg['voice']}" + (f" (ЗАПАСНОЙ вместо {osnovnoj})" if voice else ""))
    for s in segs:
        print(f"  {s['id']:8s} {s['start']:5.2f} +{s['dur']:.2f}")

if __name__ == "__main__":
    main(sys.argv[1])
