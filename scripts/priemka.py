"""Машинная приёмка ролика — подсказка, не проверка (Р715, п.62). Готовый .mp4 -> отчёт по-русски о техническом браке:
- звук: есть ли дорожка; паузы тишины длиннее 1,5 с со временем (silencedetect); громкость против -16 LUFS (ebur128, EBU R128);
- длина: ролик против заявленной (timeline.json total — по нему Root.tsx задаёт длину, или --dlina);
- субтитры: конец последней строки .srt/.vtt против конца голоса (<prefix>-golos.mp3 из sloi_zvuka.py, иначе звук ролика);
- кадр: чёрные участки (blackdetect).
Смысл, картинки и голос по содержанию — по-прежнему глазами. Ничего не останавливает: код выхода всегда 0 (Р627),
в render.yml — необязательный шаг continue-on-error; есть $GITHUB_STEP_SUMMARY — отчёт пишется и в сводку прогона.
Как в мире: EBU R128 (https://tech.ebu.ch/publications/r128), ffmpeg ebur128/silencedetect/blackdetect
(https://ffmpeg.org/ffmpeg-filters.html), автоматический QC перед ручным просмотром — Netflix Photon/IMF, YouTube ~-14 LUFS.
Запуск: python scripts/priemka.py <ролик.mp4> [...] [--timeline <timeline.json>] [--dlina <с>] [--srt <файл>] [--json <файл>]
Без --timeline берётся public/days/<день>/timeline.json по имени out/<день>-<вариант>-<формат>.mp4, если он есть."""
import json, os, re, subprocess, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import zvuk

ROOT = pathlib.Path(__file__).resolve().parent.parent
TISHINA = 1.5      # с — пауза длиннее заметна зрителю (п.62)
POROG = zvuk.POROG  # -45dB — тот же порог тишины, что у гида
LUFS, DOPUSK = zvuk.LUFS, 2.0   # цель -16 LUFS ±2 (веб: -14…-18)
PIK = -1.0         # dBTP — выше риск искажения после сжатия площадкой
DLINA_DOPUSK = 0.5   # с — расхождение длины с заявленной
SUB_DOPUSK = 1.0     # с — конец субтитров против конца голоса
CHERNOTA = 0.5       # с — чёрный участок длиннее заметен


def dlit(f):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True).stdout.strip()
    return float(o) if o else None


def dorozhki(f):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True).stdout.split()
    return {"video": o.count("video"), "audio": o.count("audio")}


def tishina(f, d=TISHINA):
    e = zvuk.ff("-i", str(f), "-vn", "-af", f"silencedetect=noise={POROG}:d={d}", "-f", "null", "-")
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    return [(max(a, 0.0), en[k] if k < len(en) else None) for k, a in enumerate(st)]


def konec_golosa(f, total):
    """конец последнего звука: начало тишины, что тянется до конца файла (порог 0,3 с), иначе конец файла"""
    t = tishina(f, 0.3)
    if t and (t[-1][1] is None or t[-1][1] >= total - 0.05):
        return round(t[-1][0], 2)
    return round(total, 2)


def chernota(f):
    e = zvuk.ff("-i", str(f), "-an", "-vf", f"blackdetect=d={CHERNOTA}:pix_th=0.10", "-f", "null", "-")
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", e)]


def konec_sub(p):
    t = re.findall(r"-->\s*(\d+):(\d+):(\d+)[,.](\d+)", pathlib.Path(p).read_text(encoding="utf-8", errors="replace"))
    return max((int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000 for h, m, s, ms in t), default=None)


def mm(x):
    return f"{int(x // 60)}:{x % 60:04.1f}"


def ryadom(f, opc):
    """timeline, субтитры и голос по имени out/<день>-<вариант>-<формат>.mp4 (render.mjs, sloi_zvuka.py)"""
    stem = re.sub(r"-(16x9|9x16)$", "", f.stem)
    day = stem.rsplit("-", 1)[0] if re.search(r"-[A-Z]$", stem) else stem
    tl = opc.get("timeline") or ROOT / "public/days" / day / "timeline.json"
    srt = opc.get("srt") or next((p for p in (f.with_suffix(".srt"), f.with_suffix(".vtt"),
                                              f.with_name(f"{stem}-16x9.srt"), f.with_name(f"{stem}-16x9.vtt")) if p.exists()), None)
    golos = next((p for p in (f.with_name(f"{stem}-16x9-golos.mp3"), f.with_name(f.stem + "-golos.mp3")) if p.exists()), None)
    return pathlib.Path(tl) if pathlib.Path(tl).exists() else None, srt, golos


def priemka(f, opc):
    f = pathlib.Path(f)
    r = {"fajl": f.name, "zamechaniya": [], "stroki": []}
    z, s = r["zamechaniya"], r["stroki"]
    total = dlit(f)
    if total is None:
        z.append("ffprobe не прочёл файл"); return r
    r["dlina"] = round(total, 2)
    d = dorozhki(f)
    tl, srt, golos = ryadom(f, opc)

    # длина
    zayav = opc.get("dlina") or (json.loads(tl.read_text())["total"] if tl else None)
    if zayav:
        raz = total - float(zayav)
        s.append(f"длина {total:.1f} с, заявлено {float(zayav):.1f} с ({'timeline.json' if not opc.get('dlina') else '--dlina'}), разница {raz:+.1f} с")
        if abs(raz) > DLINA_DOPUSK: z.append(f"длина расходится с заявленной на {raz:+.1f} с")
    else:
        s.append(f"длина {total:.1f} с (заявленной нет: ни timeline.json, ни --dlina)")

    # звук
    if not d["audio"]:
        z.append("нет дорожки звука"); s.append("звук: дорожки нет")
    else:
        s.append(f"звук: дорожек {d['audio']}")
        l = zvuk.lufs(f)
        r["lufs"] = l
        s.append(f"громкость {l['I']:.1f} LUFS (цель {LUFS:.0f} ±{DOPUSK:.0f}), разброс LRA {l['LRA']:.1f} LU, пик {l['pik']:.1f} dBFS")
        if abs(l["I"] - LUFS) > DOPUSK: z.append(f"громкость {l['I']:.1f} LUFS — {'тише' if l['I'] < LUFS else 'громче'} цели {LUFS:.0f} на {abs(l['I'] - LUFS):.1f} LU")
        if l["pik"] > PIK: z.append(f"пик {l['pik']:.1f} dBFS выше {PIK:.0f} — возможен хрип после сжатия площадкой")
        t = tishina(f)
        r["tishina"] = [[round(a, 2), round(b if b is not None else total, 2)] for a, b in t]
        if t:
            sp = ", ".join(f"{mm(a)}–{mm(b if b is not None else total)} ({(b if b is not None else total) - a:.1f} с)" for a, b in t)
            s.append(f"тишина длиннее {TISHINA} с: {sp}")
            z.append(f"участков тишины длиннее {TISHINA} с: {len(t)}")
        else:
            s.append(f"тишины длиннее {TISHINA} с нет")

        # субтитры против голоса
        if srt:
            ks = konec_sub(srt)
            src = golos or f
            kg = konec_golosa(src, dlit(src) or total)
            if ks is None:
                z.append(f"в {pathlib.Path(srt).name} нет строк"); s.append("субтитры: файл пуст")
            else:
                raz = ks - kg
                s.append(f"субтитры ({pathlib.Path(srt).name}) кончаются в {mm(ks)}, голос ({'слой голоса' if golos else 'звук ролика'}) — в {mm(kg)}, разница {raz:+.1f} с")
                if abs(raz) > SUB_DOPUSK: z.append(f"конец субтитров расходится с концом голоса на {raz:+.1f} с")
        else:
            s.append("субтитров рядом нет (.srt/.vtt) — сверка с голосом пропущена")

    # кадр
    if d["video"]:
        b = chernota(f)
        r["chernota"] = [[round(x, 2), round(y, 2)] for x, y in b]
        if b:
            s.append("чёрные кадры: " + ", ".join(f"{mm(x)}–{mm(y)} ({y - x:.1f} с)" for x, y in b))
            z.append(f"чёрных участков длиннее {CHERNOTA} с: {len(b)}")
        else:
            s.append(f"чёрных участков длиннее {CHERNOTA} с нет")
    else:
        z.append("нет видеодорожки")
    return r


def otchet(r):
    zag = f"### {r['fajl']} — " + ("замечаний нет" if not r["zamechaniya"] else f"замечаний {len(r['zamechaniya'])}: " + "; ".join(r["zamechaniya"]))
    return "\n".join([zag, *(f"- {x}" for x in r["stroki"]), ""])


if __name__ == "__main__":
    a, opc, fajly = sys.argv[1:], {}, []
    while a:
        x = a.pop(0)
        if x in ("--timeline", "--dlina", "--srt", "--json") and a: opc[x[2:]] = a.pop(0)
        else: fajly.append(x)
    out = ["## Приёмка ролика (подсказка, ничего не останавливает)", ""]
    vse = []
    for f in fajly:
        try:
            r = priemka(f, opc)
        except Exception as e:  # подсказка не роняет прогон
            r = {"fajl": pathlib.Path(f).name, "zamechaniya": [f"замер не удался: {str(e).splitlines()[0] if str(e) else type(e).__name__}"], "stroki": []}
        vse.append(r); out.append(otchet(r))
    txt = "\n".join(out)
    print(txt)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as h: h.write(txt + "\n")
    if opc.get("json"): pathlib.Path(opc["json"]).write_text(json.dumps(vse, ensure_ascii=False, indent=1))
    sys.exit(0)
