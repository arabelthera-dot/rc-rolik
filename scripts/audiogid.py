"""Озвучка аудиогида (r310): transcript-yaml -> out/audiogid/<den>.mp3 + <den>.json (длительности абзацев).
Голос, ударения и повторы — те же, что у роликов (scripts/tts.py, udareniya.json).
Вход: yaml дня сайта (audioguide.transcript) или отдельный yaml с верхним transcript; абзацы — строки с <p>…</p>."""
import asyncio, json, sys, re, subprocess, pathlib, random, time, html
import yaml
from tts import synth, udar, dur, TRIES

GAP = 0.6  # пауза между абзацами, с

def abzacy(path):
    d = yaml.safe_load(pathlib.Path(path).read_text())
    tr = (d.get("audioguide") or {}).get("transcript") or d.get("transcript")
    if not tr:
        sys.exit(f"{path}: нет transcript (ни audioguide.transcript, ни transcript)")
    den = str(d.get("den") or d.get("date") or pathlib.Path(path).stem)
    return den, [html.unescape(re.sub(r"<[^>]+>", "", p)).strip().strip("«»").strip() for p in tr]

def main(path, voice, rate, outdir):
    den, txt = abzacy(path)
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    parts, segs, t = [], [], 0.0
    for i, s in enumerate(txt):
        mp3 = out / f"{den}-p{i}.mp3"
        for k in range(TRIES):  # повтор с растущей паузой, как в tts.py (r260, r264)
            try:
                words = asyncio.run(synth(udar(s), voice, rate, mp3))
                if not words or mp3.stat().st_size < 1000: raise RuntimeError("пустой ответ")
                break
            except Exception as e:
                if k == TRIES - 1: raise
                p = min(3 * 2 ** k, 60) + random.uniform(0, 3)
                print(f"  абзац {i}: попытка {k + 1} из {TRIES} — {type(e).__name__}, жду {p:.0f} с", flush=True)
                time.sleep(p)
        # все ли фразы озвучены: число слов от службы против слов в тексте
        src = len([w for w in s.split() if re.search(r"\w", w)])
        d = dur(mp3)
        segs.append({"i": i, "start": round(t, 2), "dur": round(d, 2), "slov_tekst": src, "slov_golos": len(words)})
        print(f"  абзац {i}: {t:6.1f} +{d:5.1f} с, слов {len(words)}/{src}", flush=True)
        parts.append(mp3); t += d + GAP
    lst = out / "list.txt"
    sil = out / "gap.mp3"
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", str(GAP), "-c:a", "libmp3lame", "-b:a", "48k", str(sil)])
    lst.write_text("".join(f"file '{p.name}'\n" + (f"file '{sil.name}'\n" if k < len(parts) - 1 else "") for k, p in enumerate(parts)))
    full = out / f"{den}.mp3"
    subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", str(full)])
    lst.unlink(); sil.unlink()
    total = dur(full)
    (out / f"{den}.json").write_text(json.dumps({"den": den, "voice": voice, "rate": rate, "total": round(total, 2), "abzacy": segs}, ensure_ascii=False, indent=1))
    plohie = [s["i"] for s in segs if s["slov_golos"] < 0.9 * s["slov_tekst"]]
    print(f"{den}: {total:.1f} с, абзацев {len(segs)}")
    if plohie:
        sys.exit(f"абзацы озвучены не полностью: {plohie}")

if __name__ == "__main__":
    main(*sys.argv[1:5])
