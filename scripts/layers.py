"""2.5D: каждый подлинный кадр -> bg.jpg (фон, передний план заделан inpaint) + fg.png (передний план с альфой).
Передний план: band — нижняя полоса с мягким краем; fg_rect — GrabCut по прямоугольнику fg_rect из days/<id>.json (доли ширины/высоты)."""
import json, sys, pathlib
import cv2, numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJ = ROOT.parent.parent  # ~/projects/russian-civilization
TARGET = 2200  # длинная сторона после увеличения

def up(img):
    h, w = img.shape[:2]
    k = TARGET / max(h, w)
    img = cv2.resize(img, (int(w * k), int(h * k)), interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(img, (0, 0), 2.0)
    return cv2.addWeighted(img, 1.35, blur, -0.35, 0)  # лёгкая резкость после увеличения

def main(day):
    cfg = json.loads((ROOT / "days" / f"{day}.json").read_text())
    out = ROOT / "public" / "days" / day
    out.mkdir(parents=True, exist_ok=True)
    meta = {}
    for key, im in cfg["images"].items():
        img = cv2.imread(str(PROJ / im["src"]))
        if im.get("crop"):  # [x0,y0,x1,y1] доли — убрать водяные знаки/поля
            h, w = img.shape[:2]; x0, y0, x1, y1 = im["crop"]
            img = img[int(y0*h):int(y1*h), int(x0*w):int(x1*w)]
        img = up(img)
        h, w = img.shape[:2]
        cv2.imwrite(str(out / f"{key}-bg.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        meta[key] = {"w": w, "h": h, "fg": False, "label": im.get("label")}
        if im.get("parallax") is False:  # кадр без переднего плана — нет шва полосы (напр. караван)
            continue
        if im.get("band"):  # пейзаж: передний план — нижняя полоса кадра (земля, люди, повозки)
            y0 = int(im["band"] * h); fe = int(0.06 * h)
            ramp = np.clip((np.arange(h) - y0) / fe, 0, 1)
            m = (np.tile(ramp[:, None], (1, w)) * 255).astype(np.uint8)
            rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA); rgba[:, :, 3] = m
            cv2.imwrite(str(out / f"{key}-fg.png"), rgba)
            meta[key]["fg"] = True
            continue
        r = im.get("fg_rect")
        if not r:
            continue
        small = cv2.resize(img, (w // 3, h // 3))
        mask = np.zeros(small.shape[:2], np.uint8)
        sh, sw = small.shape[:2]
        rect = (int(r[0]*sw), int(r[1]*sh), max(1, int((r[2]-r[0])*sw) - 1), max(1, int((r[3]-r[1])*sh) - 1))
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(small, mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
        m = np.where((mask == 1) | (mask == 3), 255, 0).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        # оставить только крупные куски
        n, lab, st, _ = cv2.connectedComponentsWithStats(m)
        keep = np.zeros_like(m)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] > 0.01 * sw * sh:
                keep[lab == i] = 255
        m = cv2.resize(keep, (w, h), interpolation=cv2.INTER_LINEAR)
        m = cv2.GaussianBlur(m, (0, 0), 2.5)
        rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA); rgba[:, :, 3] = m
        cv2.imwrite(str(out / f"{key}-fg.png"), rgba)
        # фон: заделать место переднего плана, чтобы при сдвиге не было «дыры»
        hole = cv2.dilate((m > 40).astype(np.uint8) * 255, np.ones((25, 25), np.uint8))
        bg = cv2.inpaint(cv2.resize(img, (w // 2, h // 2)), cv2.resize(hole, (w // 2, h // 2)), 9, cv2.INPAINT_TELEA)
        bg = cv2.resize(bg, (w, h)); hole3 = (cv2.GaussianBlur(hole, (0, 0), 6) / 255.0)[..., None]
        bg = (img * (1 - hole3) + bg * hole3).astype(np.uint8)
        cv2.imwrite(str(out / f"{key}-bg.jpg"), bg, [cv2.IMWRITE_JPEG_QUALITY, 90])
        meta[key]["fg"] = True
        cv2.imwrite(str(out / f"_mask-{key}.jpg"), cv2.resize(m, (w // 4, h // 4)))
    (out / "images.json").write_text(json.dumps(meta, indent=1))
    print(meta)

if __name__ == "__main__":
    main(sys.argv[1])
