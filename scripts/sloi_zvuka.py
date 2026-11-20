"""Слои звука рядом с роликом (r713 п.65, п.66): public/days/<id>/ -> <prefix>-golos.mp3 (голос), <prefix>-shum.mp3
(музыка и шумы sfx.wav с той же громкостью 0.55, что в mix.mp3, до общего выравнивания), <prefix>.srt и <prefix>.vtt
(субтитры по словам). Ролик не меняется; голос + шум = mix.mp3 без loudnorm.
Субтитры — из слов edge-tts (tts.py: voice.srt/.vtt). Слов нет (старый ролик, голос не из tts.py) — только с --whisper
слова распознаёт faster-whisper (бесплатно, на процессоре) по voice.mp3 или mix.mp3 и пишет voice.words.json/.srt/.vtt
в том же виде, что tts.py. Без --whisper и без слов — субтитров нет, слои голоса и шума всё равно ложатся.
Запуск: python scripts/sloi_zvuka.py <день> <prefix>  [--whisper]   напр. ns02feb out/ns02feb-A-16x9"""
import json, os, sys, subprocess, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHUM = 0.55  # громкость подложки в сведении — как в sfx.py
MODEL = os.environ.get("WHISPER_MODEL", "small")  # faster-whisper: small на процессоре — минута звука за ~десятки секунд, русский разбирает


def ts(x, sep):
    ms = int(round(x * 1000)); return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}{sep}{ms % 1000:03d}"


def slova(d, ws):
    """Тот же вид, что tts.py slova(): по слову на строку субтитров."""
    (d / "voice.words.json").write_text(json.dumps(ws, ensure_ascii=False, indent=0))
    cue = lambda w, sep: f"{ts(w['t'], sep)} --> {ts(w['t'] + max(w['d'], 0.05), sep)}\n{w['w']}\n"
    (d / "voice.srt").write_text("\n".join(f"{k + 1}\n" + cue(w, ",") for k, w in enumerate(ws)))
    (d / "voice.vtt").write_text("WEBVTT\n\n" + "\n".join(cue(w, ".") for w in ws))


def whisper(d):
    zvuk = next((d / f for f in ("voice.mp3", "mix.mp3") if (d / f).exists()), None)
    if not zvuk:
        sys.exit(f"{d.name}: нет ни voice.mp3, ни mix.mp3 — распознавать нечего")
    from faster_whisper import WhisperModel
    m = WhisperModel(MODEL, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(zvuk), language="ru", word_timestamps=True, vad_filter=True)
    ws = [{"t": round(w.start, 3), "d": round(w.end - w.start, 3), "w": w.word.strip()}
          for s in segs for w in (s.words or []) if w.word.strip()]
    if not ws:
        sys.exit(f"{d.name}: whisper не нашёл слов в {zvuk.name}")
    slova(d, ws)
    print(f"{d.name}: субтитры whisper по {zvuk.name} — {len(ws)} слов")


def main(day, prefix, mozhno_whisper):
    d = ROOT / "public" / "days" / day
    pre = pathlib.Path(prefix); pre.parent.mkdir(parents=True, exist_ok=True)
    ff = ["ffmpeg", "-y", "-v", "error"]
    if not (d / "voice.mp3").exists():
        sys.exit(f"{day}: нет public/days/{day}/voice.mp3 — слоя голоса нет")
    shutil.copyfile(d / "voice.mp3", f"{pre}-golos.mp3")
    lozh = ["голос"]
    if (d / "sfx.wav").exists():
        subprocess.check_call(ff + ["-i", str(d / "sfx.wav"), "-af", f"volume={SHUM}", "-ar", "48000",
                               "-c:a", "libmp3lame", "-b:a", "160k", f"{pre}-shum.mp3"])
        lozh.append("шум")
    if not (d / "voice.srt").exists() and mozhno_whisper:
        whisper(d)
    if (d / "voice.srt").exists():
        for x in ("srt", "vtt"):
            shutil.copyfile(d / f"voice.{x}", f"{pre}.{x}")
        lozh.append("субтитры")
    else:
        print(f"{day}: слов нет (voice.srt) — субтитров нет; распознать: --whisper")
    print(f"{day}: слои {', '.join(lozh)} -> {pre}-*")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], a[1], "--whisper" in sys.argv)
