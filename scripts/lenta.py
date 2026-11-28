"""Черновая лента кадров (п.61): days/<id>.json -> out/lenta/<id>.png — все сцены одной сеткой, без рендера.

Плитка = кадр сцены с кропом из images, номер, id, приём (fx) и длительность. Длительность — из
public/days/<id>/timeline.json, если озвучка уже была; иначе оценка «≈» по длине текста (~15 знаков/с при +18%).
--oblozhka (п.70): кандидат обложки по резкости (дисперсия лапласиана), контрасту и насыщенности —
только предложение в out/lenta/<id>-oblozhka.json, обложки и ролики не меняются.

  python3 scripts/lenta.py 02feb [--cfg путь.json] [--out папка] [--oblozhka]
"""
import argparse, json, pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
TW, TH, BAR, COLS, PAD = 480, 270, 34, 4, 10
ZNAKOV_V_SEK = 15.0


def font(size):
    f = ImageFont.truetype(str(ROOT / "public/fonts/Inter.ttf"), size)
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def kadr(images, key):
    """Кадр с кропом [x0, y0, x1, y1] в долях — как его берёт ролик."""
    im = images.get(key) if key else None
    if not im:
        return None
    pic = ImageOps.exif_transpose(Image.open(ROOT / im["src"])).convert("RGB")
    x0, y0, x1, y1 = im.get("crop", [0, 0, 1, 1])
    w, h = pic.size
    return pic.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))


def ocenka(pic):
    """Резкость (дисперсия лапласиана), контраст (СКО яркости), насыщенность (среднее S в HSV)."""
    small = pic.copy()
    small.thumbnail((640, 640))
    g = np.asarray(small.convert("L"), dtype=np.float32)
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    s = np.asarray(small.convert("HSV"), dtype=np.float32)[..., 1]
    return {"rezkost": float(lap.var()), "kontrast": float(g.std()), "nasyshchennost": float(s.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("day")
    ap.add_argument("--cfg")
    ap.add_argument("--out", default=str(ROOT / "out/lenta"))
    ap.add_argument("--oblozhka", action="store_true")
    a = ap.parse_args()
    cfg = json.loads(pathlib.Path(a.cfg or ROOT / "days" / f"{a.day}.json").read_text())
    images, segs = cfg["images"], cfg["segments"]
    tl = ROOT / "public/days" / a.day / "timeline.json"
    durs = {s["id"]: s["dur"] for s in json.loads(tl.read_text())["segments"]} if tl.exists() else {}

    rows = -(-len(segs) // COLS)
    W = COLS * TW + (COLS + 1) * PAD
    H = 60 + rows * (TH + BAR + PAD) + PAD
    sheet = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    f_big, f_bar, f_small = font(28), font(20), font(16)
    total, priblizh = 0.0, False
    for i, s in enumerate(segs):
        x, y = PAD + (i % COLS) * (TW + PAD), 60 + (i // COLS) * (TH + BAR + PAD)
        pic = kadr(images, s.get("image"))
        if pic:
            sheet.paste(ImageOps.fit(pic, (TW, TH)), (x, y))
        else:
            d.rectangle((x, y, x + TW, y + TH), fill=(60, 60, 60))
            d.text((x + TW / 2, y + TH / 2), s.get("fx", "без кадра"), font=f_big, fill=(200, 200, 200), anchor="mm")
        vstavka = kadr(images, (s.get("labels") or {}).get("image"))
        if vstavka:
            mini = ImageOps.fit(vstavka, (TW // 3, TH // 3))
            sheet.paste(mini, (x + TW - mini.width - 8, y + 8))
            d.rectangle((x + TW - mini.width - 8, y + 8, x + TW - 8, y + 8 + mini.height), outline=(255, 255, 255), width=2)
        if s["id"] in durs:
            t = durs[s["id"]]
            dl = f"{t:.1f} с"
        else:
            t = len(s["say"]) / ZNAKOV_V_SEK
            dl, priblizh = f"≈{t:.1f} с", True
        total += t
        d.rectangle((x, y + TH, x + TW, y + TH + BAR), fill=(0, 0, 0))
        d.text((x + 10, y + TH + BAR / 2), f"{i + 1}. {s['id']} · {s.get('fx', '')}", font=f_bar, fill=(255, 255, 255), anchor="lm")
        d.text((x + TW - 10, y + TH + BAR / 2), dl, font=f_bar, fill=(255, 210, 80), anchor="rm")
    zag = f"{cfg['id']} · {len(segs)} сцен · {'≈' if priblizh else ''}{total:.0f} с"
    d.text((PAD, 30), zag, font=f_big, fill=(255, 255, 255), anchor="lm")
    d.text((W - PAD, 30), "черновая лента, без рендера", font=f_small, fill=(150, 150, 150), anchor="rm")

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / f"{a.day}.png", optimize=True)
    print(f"{out / f'{a.day}.png'}: {zag}")

    if a.oblozhka:
        o = {k: {"src": v["src"], **ocenka(kadr(images, k))} for k, v in images.items()}
        for m in ("rezkost", "kontrast", "nasyshchennost"):
            mx = max(v[m] for v in o.values()) or 1
            for v in o.values():
                v[m + "_dolya"] = round(v[m] / mx, 3)
        for v in o.values():
            v["ball"] = round((v["rezkost_dolya"] + v["kontrast_dolya"] + v["nasyshchennost_dolya"]) / 3, 3)
        reiting = sorted(o, key=lambda k: -o[k]["ball"])
        pred = {"day": cfg["id"], "kandidat": reiting[0], "src": o[reiting[0]]["src"],
                "pravilo": "ball = среднее долей от лучшего по резкости (дисперсия лапласиана), контрасту (СКО яркости), насыщенности (S в HSV); только предложение",
                "reiting": [{"key": k, **o[k]} for k in reiting]}
        (out / f"{a.day}-oblozhka.json").write_text(json.dumps(pred, ensure_ascii=False, indent=1))
        print(f"кандидат обложки: {reiting[0]} ({o[reiting[0]]['src']}), балл {o[reiting[0]]['ball']}")
        for k in reiting:
            print(f"  {k:10s} балл {o[k]['ball']:.3f}  резк {o[k]['rezkost']:.0f}  контр {o[k]['kontrast']:.1f}  насыщ {o[k]['nasyshchennost']:.1f}")


if __name__ == "__main__":
    main()
