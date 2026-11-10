#!/usr/bin/env python3
"""Чистка царапин и пыли старого скана и дорисовка краёв до 9:16 (r716 п.93) — бесплатно, локально, на OpenCV.

scripts/carapiny.py <кадр.jpg>... [--chistka] [--kraya razmytie|otrazhenie] [--linii] [--out out/carapiny] [--pokaz]
  по умолчанию выключено всё: без --chistka и --kraya скрипт только печатает замер (доля пыли/царапин).
  --chistka — пыль и тонкие царапины: отклонение от медианы 7×7 (как фильтр «Пыль и царапины» в Photoshop),
              в маску идут только одиночные (в 6 раз сильнее фона вокруг — растр и штрихи
              гравюры не идут) мелкие пятна (до 0.02 % кадра) вдали от краёв рисунка;
              тонкие длинные линии (до 3 px) — только с --linii: по форме царапину не отличить от мачты или провода;
              маска больше 1.5 % кадра — это штрихи гравюры, а не пыль: кадр не трогается. Заделка — cv2.inpaint
              (Telea 2004, радиус 3).
  --kraya — кадр целиком вписывается в 1080×1920, пустые поля: «razmytie» — тот же кадр на весь экран,
            размыт и притемнён (как вертикальные ролики из горизонтальных видео); «otrazhenie» — зеркальное
            продолжение краёв (BORDER_REFLECT) с размытием, растущим от шва. Генеративной модели нет.
  --pokaz — рядом кладёт <имя>-do-posle.jpg: слева «до», справа «после», маска — красным.
Пишет только в --out; кадры в kadry/, days/*.json, ролик и CI не меняются — в конвейер скрипт не включён.
"""
import argparse, sys
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
PYL = 0.0002     # пятно пыли — до 0.02 % площади кадра
TOLSHCHINA = 3   # царапина — линия не толще 3 px
POROG = 30.0      # отклонение от медианы — от 30 уровней яркости из 255
ODINOCHKA = 6.0   # и в 6 раз сильнее среднего отклонения в окне 31×31: пятно одиночное, не узор
POTOLOK = 0.015  # маска больше 1.5 % кадра — это рисунок, не пыль


def maska(img, linii=False):
    """Маска пыли и царапин: пиксели, сильно отличные от медианы соседей, только мелкие или тонкие куски."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    med = cv2.medianBlur(g, 7)
    d = cv2.absdiff(g, med).astype(np.float32)
    fon = cv2.blur(d, (31, 31))  # сколько «мелочи» вокруг: у растра и штрихов гравюры её много, у пыли на ровном — нет
    m = ((d > POROG) & (d > ODINOCHKA * fon)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    plosh = g.size
    # настоящий рисунок: края медианного кадра (пыль медиана стирает, борт и палуба остаются) — рядом с ними не трогаем
    kraj = cv2.dilate(cv2.Canny(cv2.GaussianBlur(med, (5, 5), 0), 20, 60), np.ones((9, 9), np.uint8))
    pole = max(3, round(0.01 * min(g.shape)))  # обрез скана — не пыль
    kraj[:pole], kraj[-pole:], kraj[:, :pole], kraj[:, -pole:] = 255, 255, 255, 255
    tonk = cv2.erode(m, np.ones((TOLSHCHINA + 1, TOLSHCHINA + 1), np.uint8))  # что переживёт эрозию — толще линии
    tolstye = set(np.unique(lab[tonk > 0]))
    out = np.zeros_like(m)
    for i in range(1, n):
        x, y, w, h, a = st[i]
        dlina = max(w, h)
        melkoe = a <= PYL * plosh
        if kraj[lab == i].any():
            continue
        liniya = linii and i not in tolstye and dlina >= 15 and a <= dlina * TOLSHCHINA
        if melkoe or liniya:
            out[lab == i] = 1
    return out


def chistka(img, linii=False):
    m = maska(img, linii)
    dolya = float(m.mean())
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))  # заделка с запасом в 1 px — без ореола по краю пятна
    if dolya > POTOLOK:
        return img, m, dolya, False
    return cv2.inpaint(img, m * 255, 3, cv2.INPAINT_TELEA), m, dolya, True


def vpisat(img):
    h, w = img.shape[:2]
    k = min(W / w, H / h)
    nw, nh = round(w * k), round(h * k)
    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4 if k > 1 else cv2.INTER_AREA), (W - nw) // 2, (H - nh) // 2


def kraya(img, kak):
    fg, x0, y0 = vpisat(img)
    nh, nw = fg.shape[:2]
    if kak == "razmytie":
        k = max(W / img.shape[1], H / img.shape[0])
        bg = cv2.resize(img, (round(img.shape[1] * k), round(img.shape[0] * k)), interpolation=cv2.INTER_AREA)
        by, bx = (bg.shape[0] - H) // 2, (bg.shape[1] - W) // 2
        bg = cv2.GaussianBlur(bg[by:by + H, bx:bx + W], (0, 0), 40)
        bg = (bg * 0.55).astype(np.uint8)
    else:
        bg = cv2.copyMakeBorder(fg, y0, H - nh - y0, x0, W - nw - x0, cv2.BORDER_REFLECT)
        sil = cv2.GaussianBlur(bg, (0, 0), 25)
        # чем дальше от шва — тем сильнее размытие и тень: отражение не спорит с подлинным кадром
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dist = np.maximum(np.maximum(y0 - yy, yy - (y0 + nh - 1)), np.maximum(x0 - xx, xx - (x0 + nw - 1)))
        t = np.clip(dist / 120.0, 0, 1)[..., None]
        bg = (bg * (1 - t) + sil * t) * (1 - 0.45 * np.clip(dist / max(1, max(y0, x0)), 0, 1))[..., None]
        bg = bg.astype(np.uint8)
    bg[y0:y0 + nh, x0:x0 + nw] = fg
    return bg


def pokaz(do, posle, m):
    h = 960
    a = cv2.resize(do, (round(do.shape[1] * h / do.shape[0]), h))
    b = cv2.resize(posle, (round(posle.shape[1] * h / posle.shape[0]), h))
    if m is not None and do.shape[:2] == m.shape:
        r = cv2.resize(m, (a.shape[1], h), interpolation=cv2.INTER_NEAREST) > 0
        a = a.copy()
        a[r] = (0, 0, 255)
    return np.hstack([a, np.full((h, 12, 3), 255, np.uint8), b])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kadry", nargs="+")
    p.add_argument("--chistka", action="store_true")
    p.add_argument("--kraya", choices=["razmytie", "otrazhenie"])
    p.add_argument("--out", default=str(ROOT / "out" / "carapiny"))
    p.add_argument("--linii", action="store_true")
    p.add_argument("--pokaz", action="store_true")
    a = p.parse_args()
    out = Path(a.out)
    for f in a.kadry:
        img = cv2.imread(f, cv2.IMREAD_COLOR)
        if img is None:
            sys.exit(f"не читается: {f}")
        res, m = img, None
        zametka = []
        if a.chistka or not a.kraya:
            chist, m, dolya, sdelano = chistka(img, a.linii)
            zametka.append(f"маска {dolya * 100:.2f} % ({int(m.sum())} px)" + ("" if sdelano or not a.chistka else ", выше потолка — не трогал"))
            if a.chistka:
                res = chist
        if a.kraya:
            res = kraya(res, a.kraya)
            zametka.append(f"края {a.kraya} → {W}×{H}")
        print(f"{f}: {img.shape[1]}×{img.shape[0]}, " + "; ".join(zametka))
        if not (a.chistka or a.kraya):
            continue
        out.mkdir(parents=True, exist_ok=True)
        st = Path(f).stem
        cv2.imwrite(str(out / f"{st}-posle.jpg"), res, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if a.pokaz:
            cv2.imwrite(str(out / f"{st}-do-posle.jpg"), pokaz(img, res, m if not a.kraya else None), [cv2.IMWRITE_JPEG_QUALITY, 88])
            if a.chistka and a.kraya:
                cv2.imwrite(str(out / f"{st}-maska.jpg"), pokaz(img, chistka(img, a.linii)[0], m), [cv2.IMWRITE_JPEG_QUALITY, 88])


if __name__ == "__main__":
    main()
