#!/usr/bin/env python3
"""Точка главного предмета для обрезки 9:16 (r713 п.72) — считает машина, бесплатно, на OpenCV.

scripts/tochka.py <день> [--zapisat] [--pokaz <папка>]
  лицо есть (YuNet — детектор лиц из opencv_zoo, MIT, scripts/modeli/) — точка на самом крупном лице;
  лица нет — центр тяжести карты заметности spectral residual (Hou, Zhang 2007; то же, что
  cv2.saliency.StaticSaliencySpectralResidual из opencv-contrib, здесь — на numpy).
Точка — доли 0..1 кадра после crop (как режет scripts/layers.py), с отступом 0.1 от края.
Без ключей печатает предложение; --zapisat — пишет images[k].fokus {x, y, kak} в days/<день>.json;
--pokaz — кладёт кадры с отмеченной точкой и окном 9:16 в папку, чтобы проверить глазами.
Ролик точку не берёт, пока в дне нет "fokus_9x16": true (src/Video.tsx) — вид готовых роликов прежний.
"""
import json, sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "scripts" / "modeli" / "face_detection_yunet_2023mar.onnx"


def zametnost(img):
    g = cv2.cvtColor(cv2.resize(img, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32)
    f = np.fft.fft2(g)
    amp = np.log(np.abs(f) + 1e-9)
    ost = amp - cv2.blur(amp, (3, 3))
    s = np.abs(np.fft.ifft2(np.exp(ost + 1j * np.angle(f)))) ** 2
    s = cv2.GaussianBlur(s, (9, 9), 2.5)
    s[s < s.mean() * 2] = 0  # только заметное — фон не тянет точку к центру
    return s / (s.max() + 1e-9)


def tochka(img):
    h, w = img.shape[:2]
    k = 800 / max(h, w)
    sm = cv2.resize(img, (int(w * k), int(h * k))) if k < 1 else img
    det = cv2.FaceDetectorYN.create(str(MODEL), "", (sm.shape[1], sm.shape[0]), 0.8)
    _, lica = det.detect(sm)
    lica = [] if lica is None else [r for r in lica if r[2] >= sm.shape[1] / 30]  # мелкие лица толпы — не главный предмет
    if len(lica):
        x, y, fw, fh = max(lica, key=lambda r: r[2] * r[3])[:4]
        px, py, kak = (x + fw / 2) / sm.shape[1], (y + fh / 2) / sm.shape[0], "lico"
    else:
        s = zametnost(img)
        ys, xs = np.mgrid[0:s.shape[0], 0:s.shape[1]]
        px, py, kak = (xs * s).sum() / s.sum() / s.shape[1], (ys * s).sum() / s.sum() / s.shape[0], "zametnost"
    return round(min(0.9, max(0.1, float(px))), 3), round(min(0.9, max(0.1, float(py))), 3), kak


def main(day, zapisat=False, pokaz=None):
    put = ROOT / "days" / f"{day}.json"
    tekst = put.read_text()
    cfg = json.loads(tekst)
    otstup = len(tekst.split("\n")[1]) - len(tekst.split("\n")[1].lstrip())  # отступ файла сохраняем
    if pokaz:
        Path(pokaz).mkdir(parents=True, exist_ok=True)
    for key, im in cfg["images"].items():
        img = cv2.imread(str(ROOT / im["src"]))
        if img is None:
            print(f"{key}: нет картинки {im['src']}", file=sys.stderr); continue
        if im.get("crop"):  # [x0,y0,x1,y1] доли — та же обрезка, что в layers.py
            h, w = img.shape[:2]; x0, y0, x1, y1 = im["crop"]
            img = img[int(y0*h):int(y1*h), int(x0*w):int(x1*w)]
        x, y, kak = tochka(img)
        print(f"{day} {key}: x={x} y={y} ({kak}) {im['src']}")
        if zapisat:
            im["fokus"] = {"x": x, "y": y, "kak": kak}
        if pokaz:
            h, w = img.shape[:2]
            ow = min(w, int(h * 9 / 16)); ox = int(min(max(0, x * w - ow / 2), w - ow))  # окно 9:16 на всю высоту
            v = img.copy()
            cv2.rectangle(v, (ox, 0), (ox + ow - 1, h - 1), (75, 184, 242), max(2, w // 300))
            r = max(8, w // 60)
            cv2.circle(v, (int(x * w), int(y * h)), r, (0, 0, 255), -1)
            cv2.circle(v, (int(x * w), int(y * h)), r * 2, (255, 255, 255), max(2, r // 4))
            cv2.imwrite(str(Path(pokaz) / f"{day}-{key}.jpg"), v, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if zapisat:
        put.write_text(json.dumps(cfg, ensure_ascii=False, indent=otstup or 2) + "\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0].startswith("-"):
        sys.exit("запуск: scripts/tochka.py <день> [--zapisat] [--pokaz <папка>]")
    main(a[0], "--zapisat" in a, a[a.index("--pokaz") + 1] if "--pokaz" in a else None)
