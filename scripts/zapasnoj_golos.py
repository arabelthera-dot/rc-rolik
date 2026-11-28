"""Запасной голос (п.92): edge-tts не отвечает после всех повторов tts.py — сцену озвучивает локальный бесплатный Piper.
Выключен по умолчанию; включает ZAPASNOJ_GOLOS=piper (в render.yml — вход zapasnoj_golos). Голос — PIPER_GOLOS
(ru_RU-dmitri-medium; есть ru_RU-irina-medium, ru_RU-denis-medium, ru_RU-ruslan-medium), модель кладётся в .piper/golosa/.
Piper не отдаёт границ слов — время слова раскладывается внутри предложения по длине слова (для подписей хватает).
Проба: PYTHONPATH=<где piper-tts> python scripts/zapasnoj_golos.py "текст" out.mp3"""
import os, sys, re, wave, pathlib, subprocess, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAPKA = pathlib.Path(os.environ.get("PIPER_PAPKA", ROOT / ".piper" / "golosa"))
GOLOS = os.environ.get("PIPER_GOLOS", "ru_RU-dmitri-medium")  # мужской, как ru-RU-DmitryNeural всех дней
PAUZA = 0.3  # тишина между предложениями, с
_V = {}

def vklyuchen():
    return os.environ.get("ZAPASNOJ_GOLOS", "").lower() == "piper"

def golos():
    if not _V:
        from piper import PiperVoice
        from piper.download_voices import download_voice
        model = PAPKA / f"{GOLOS}.onnx"
        if not model.exists():
            PAPKA.mkdir(parents=True, exist_ok=True)
            download_voice(GOLOS, PAPKA)
        _V["v"] = PiperVoice.load(str(model))
    return _V["v"]

def skorost(rate):
    """'+10%' edge-tts -> length_scale Piper (меньше — быстрее)."""
    m = re.fullmatch(r"([+-]\d+)%", (rate or "").strip())
    return 1 / (1 + int(m.group(1)) / 100) if m else None

def ozvuchit(text, rate, mp3):
    """Текст (со знаками ударения U+0301 — Piper их слышит) -> mp3; слова [{t, d, w}] как у edge-tts."""
    import numpy as np
    from piper import SynthesisConfig
    v = golos()
    sr = v.config.sample_rate
    pauza = np.zeros(int(PAUZA * sr), dtype=np.float32)
    sk = SynthesisConfig(length_scale=skorost(rate))
    zvuk, out, t = [], [], 0.0
    for pr in re.split(r"(?<=[.!?…])\s+", text.strip()):  # по предложению: длительность каждого известна точно
        a = np.concatenate([ch.audio_float_array for ch in v.synthesize(pr, sk)] or [pauza])
        d = len(a) / sr
        sl = [w.replace("\u0301", "") for w in re.findall(r"[\w\u0301]+(?:-[\w\u0301]+)*", pr)]
        dl = sum(len(w) + 1 for w in sl) or 1
        x = t
        for w in sl:  # внутри предложения — по длине слова
            dw = d * (len(w) + 1) / dl
            out.append({"t": round(x, 3), "d": round(dw, 3), "w": w})
            x += dw
        zvuk += [a.astype(np.float32), pauza]
        t += d + PAUZA
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        with wave.open(tmp.name, "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
            f.writeframes((np.clip(np.concatenate(zvuk or [pauza]), -1, 1) * 32767).astype(np.int16).tobytes())
        subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-i", tmp.name, "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "48k", str(mp3)])
    return out

if __name__ == "__main__":
    ws = ozvuchit(sys.argv[1], sys.argv[3] if len(sys.argv) > 3 else "+0%", sys.argv[2])
    print(f"{sys.argv[2]}: слов {len(ws)}, последнее {ws[-1] if ws else '-'}")
