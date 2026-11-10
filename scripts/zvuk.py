"""Звук после синтеза (r713, п.64 и п.91): громкость по EBU R128, паузы, границы сцен. tts.py не трогается.
- gromkost: loudnorm в два прохода (замер, затем линейная поправка) — -16 LUFS, пик -1.5 dBTP (веб и соцсети).
- pauzy: обрезка тишины в начале и в конце, паузы длиннее MAX_PAUZA сжимаются до MAX_PAUZA (silenceremove).
- granicy: паузы от MAX_PAUZA (silencedetect) -> json: сцены {i, start, end} с границей посередине паузы.
- lufs: замер целого файла (ebur128) -> I (LUFS), LRA, пик."""
import json, re, subprocess, sys, pathlib

LUFS = -16.0      # EBU R128 / веб: -16 LUFS, -14 допустимо
PIK = -2.0        # истинный пик, dBTP (mp3 при сжатии добавляет до ~1 дБ)
LRA = 11
MAX_PAUZA = 0.7   # с, длиннее — сжать (п.64)
POROG = "-45dB"   # ниже — тишина

def ff(*a):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *a], capture_output=True, text=True, check=True).stderr

def format_kak(src):
    """частота, каналы, битрейт исходного файла — выход в том же формате (у гида mp3 24 кГц моно 64k)"""
    o = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
        "stream=sample_rate,channels,bit_rate", "-of", "json", str(src)])
    s = json.loads(o)["streams"][0]
    return ["-ar", s["sample_rate"], "-ac", str(s["channels"]), "-b:a", str(int(s.get("bit_rate") or 64000) // 1000) + "k"]

def zapis(src, dst, af):
    dst = pathlib.Path(dst); tmp = dst.with_name(dst.stem + ".tmp" + dst.suffix)
    ff("-y", "-v", "error", "-i", str(src), "-af", af, *format_kak(src), "-c:a", "libmp3lame", str(tmp))
    tmp.replace(dst)

def lufs(src):
    e = ff("-i", str(src), "-af", "ebur128=peak=true", "-f", "null", "-")
    sv = e[e.rfind("Summary:"):]
    g = lambda k: float(re.search(rf"{k}:\s+(-?[\d.]+|-inf)", sv).group(1).replace("-inf", "-200"))
    return {"I": g("I"), "LRA": g("LRA"), "pik": g("Peak")}

def gromkost(src, dst=None, i=LUFS):
    """loudnorm в два прохода (так в документации ffmpeg): первый — замер, второй — линейная поправка."""
    e = ff("-i", str(src), "-af", f"loudnorm=I={i}:TP={PIK}:LRA={LRA}:print_format=json", "-f", "null", "-")
    m = json.loads(e[e.rfind("{"):e.rfind("}") + 1])
    zapis(src, dst or src, f"loudnorm=I={i}:TP={PIK}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}"
          f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")

def pauzy(src, dst=None, mx=MAX_PAUZA):
    """края — silenceremove вперёд и задом наперёд; внутри — паузы длиннее mx оставляются длиной mx.
    ffmpeg 7 оставляет от длинной паузы stop_duration + stop_silence (проба r713: 0,7+0,7 = 1,4 с), поэтому по половине."""
    kraj = f"silenceremove=start_periods=1:start_threshold={POROG}"
    zapis(src, dst or src, f"{kraj},areverse,{kraj},areverse,"
          f"silenceremove=stop_periods=-1:stop_duration={float(mx) / 2}:stop_silence={float(mx) / 2}:stop_threshold={POROG}")

def granicy(src, dst=None, mx=MAX_PAUZA):
    """сцены по паузам: граница — середина каждой паузы не короче mx."""
    e = ff("-i", str(src), "-af", f"silencedetect=noise={POROG}:d={mx}", "-f", "null", "-")
    st = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", e)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", e)]
    total = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)]))
    cut = [round((a + b) / 2, 2) for a, b in zip(st, en) if a > 0.05 and b < total - 0.05]  # тишина на краях — не граница
    t = [0.0, *cut, round(total, 2)]
    d = {"fajl": pathlib.Path(src).name, "total": round(total, 2), "porog": POROG, "min_pauza": mx,
         "sceny": [{"i": k, "start": t[k], "end": t[k + 1]} for k in range(len(t) - 1)]}
    if dst: pathlib.Path(dst).write_text(json.dumps(d, ensure_ascii=False, indent=1))
    return d

if __name__ == "__main__":
    # zvuk.py lufs <mp3>                 -> замер I/LRA/пик
    # zvuk.py gromkost <mp3> [<выход>]   -> -16 LUFS (без выхода — на месте)
    # zvuk.py pauzy <mp3> [<выход>]      -> обрезка краёв и сжатие пауз > 0,7 с
    # zvuk.py granicy <mp3> [<json>]     -> границы сцен по паузам
    cmd, *a = sys.argv[1:]
    f = {"lufs": lufs, "gromkost": gromkost, "pauzy": pauzy, "granicy": granicy}.get(cmd) or sys.exit(f"неизвестная команда {cmd}")
    r = f(*a)
    if r is not None: print(json.dumps(r, ensure_ascii=False, indent=1))
