"""Отчёт «размытые кадры дня» (п.73) — до облачного рендера, только список в out/razmytye/<день>.json.

Резкость — лапласиан из lenta.ocenka() на 640 px. Зерно скана и шум JPEG дают лапласиану ложную «резкость»,
поэтому кадр сначала чистится медианным фильтром 3×3 (зерно уходит, края остаются). Решает «kraya» —
99-й перцентиль |лапласиана| без зерна: сила самых резких краёв, ровный фон её не тянет вниз, как дисперсию.
Ниже --porog — «размыт». Доля зерна = 1 − дисперсия без зерна / сырая (из ocenka); у размытого кадра
с долей зерна от 0.5 — пометка «зерно скана»: сырая дисперсия обманула бы. Ширина кадра после кропа меньше
половины кадра ролика (960 px) — пометка «мелкий», в решение не входит. Кадры, ролики и страницы не меняются.

  python3 scripts/razmytye.py 02feb                         # кадры ролика days/02feb.json с кропом
  RC_SITE=~/rc-site python3 scripts/razmytye.py --muzei izobreteniya --key 02-01   # картинки дня на сайте
"""
import argparse, json, os, pathlib, sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from lenta import ROOT, kadr, ocenka

POROG = 40.0  # ≈10-й перцентиль «kraya» по медиатеке «Изобретений» (259 картинок, 10.11.2026)


def zamer(pic):
    small = pic.copy()
    small.thumbnail((640, 640))
    syroy = ocenka(small)["rezkost"]
    chist = small.filter(ImageFilter.MedianFilter(3))
    bez = ocenka(chist)["rezkost"]
    g = np.asarray(chist.convert("L"), dtype=np.float32)
    lap = g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:] - 4 * g[1:-1, 1:-1]
    return {"kraya": round(float(np.percentile(np.abs(lap), 99)), 1),
            "rezkost": round(syroy, 1), "rezkost_bez_zerna": round(bez, 1),
            "zerno": round(1 - bez / syroy, 2) if syroy else 0.0, "shirina": pic.width}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("day", nargs="?", help="id ролика: days/<id>.json")
    ap.add_argument("--cfg")
    ap.add_argument("--muzei")
    ap.add_argument("--key", help="ММ-ДД: все картинки public/muzei/<музей>/img/<ММ-ДД>-*")
    ap.add_argument("--site", default=os.environ.get("RC_SITE", str(ROOT.parent / "rc-site")))
    ap.add_argument("--porog", type=float, default=POROG)
    ap.add_argument("--out", default=str(ROOT / "out/razmytye"))
    a = ap.parse_args()

    if a.key:
        papka = pathlib.Path(a.site).expanduser() / "public/muzei" / a.muzei / "img"
        kadry = {p.name: ImageOps.exif_transpose(Image.open(p)).convert("RGB")
                 for p in sorted(papka.glob(f"{a.key}-*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")}
        imya, src = f"{a.muzei}-{a.key}", {k: f"/muzei/{a.muzei}/img/{k}" for k in kadry}
    else:
        cfg = json.loads(pathlib.Path(a.cfg or ROOT / "days" / f"{a.day}.json").read_text())
        kadry = {k: kadr(cfg["images"], k) for k in cfg["images"]}
        imya, src = cfg["id"], {k: v["src"] for k, v in cfg["images"].items()}

    rez = []
    for k, pic in kadry.items():
        z = {"key": k, "src": src[k], **zamer(pic)}
        z["razmyt"] = z["kraya"] < a.porog
        pometki = (["зерно скана"] if z["razmyt"] and z["zerno"] >= 0.5 else []) + \
                  (["мелкий"] if z["shirina"] < 960 else [])
        if pometki:
            z["pometki"] = pometki
        rez.append(z)
    rez.sort(key=lambda z: z["kraya"])
    razmytye = [z["key"] for z in rez if z["razmyt"]]
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{imya}.json"
    f.write_text(json.dumps({"day": imya, "porog": a.porog, "razmytye": razmytye,
                             "pravilo": "99-й перцентиль |лапласиана| после медианы 3×3 (зерно убрано), ниже порога — размыт; только список",
                             "kadry": rez}, ensure_ascii=False, indent=1))
    print(f"{f}: размытых {len(razmytye)} из {len(rez)} (порог {a.porog:g})")
    for z in rez:
        print(f"  {'РАЗМЫТ ' if z['razmyt'] else '       '}края {z['kraya']:5.1f}  дисп. {z['rezkost']:7.1f}→{z['rezkost_bez_zerna']:6.1f}  зерно {z['zerno']:.2f}"
              f"  {z['shirina']:4d}px  {z['key']}{'  [' + ', '.join(z['pometki']) + ']' if z.get('pometki') else ''}")


if __name__ == "__main__":
    main()
