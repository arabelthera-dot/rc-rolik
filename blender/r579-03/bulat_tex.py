# r579-03: процедурные текстуры булатного клинка — общий модуль (numpy; работает и в Блендере, и в обычном python3).
# Узор считается в физических координатах клинка (x — мм вдоль обуха от пяты, y — мм от обуха к лезвию),
# поэтому он непрерывен через швы атласа и одинаков на любой машине (фиксированные зёрна).
import numpy as np

LB = 820.0      # длина клинка, мм (офицерская шашка обр. 1838 «около 820 мм», donklinok.ru)
WMAX = 36.0     # ширина у пяты, мм («до 36 мм», donklinok.ru) — по поперёк ряда атласа
ROWS = 4        # атлас: клинок разрезан на 4 полосы по 205 мм, полосы стоят одна над другой
LSEG = LB / ROWS
PADU, PADV = 10 / 1024, 8 / 256   # поля вокруг полосы (против протекания мип-уровней)

# панель золотой гравировки у пяты (как на k1: золото на воронёном поле первые ~30 % клинка) — допущение по фото k1
GOLD_X0, GOLD_X1 = 14.0, 250.0


def _perm(seed):
    r = np.random.default_rng(seed)
    p = r.permutation(256)
    a = r.uniform(0, 2 * np.pi, 256)
    return np.concatenate([p, p]), np.stack([np.cos(a), np.sin(a)], 1)


def perlin(x, y, seed):
    perm, g = _perm(seed)
    xi = np.floor(x).astype(np.int64); yi = np.floor(y).astype(np.int64)
    xf = x - xi; yf = y - yi
    xi &= 255; yi &= 255
    f = lambda t: t * t * t * (t * (t * 6 - 15) + 10)
    u, v = f(xf), f(yf)

    def d(ix, iy, dx, dy):
        h = perm[perm[ix] + iy]
        return g[h, 0] * dx + g[h, 1] * dy
    n00 = d(xi, yi, xf, yf); n10 = d(xi + 1, yi, xf - 1, yf)
    n01 = d(xi, yi + 1, xf, yf - 1); n11 = d(xi + 1, yi + 1, xf - 1, yf - 1)
    a = n00 + u * (n10 - n00); b = n01 + u * (n11 - n01)
    return (a + v * (b - a)) * 1.41


def fbm(x, y, seed, oct=4, lac=2.03, gain=0.5):
    s, a, fr = 0.0, 1.0, 1.0
    for o in range(oct):
        s = s + a * perlin(x * fr + 17.3 * o, y * fr - 9.1 * o, seed + o)
        a *= gain; fr *= lac
    return s


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def uzor(x, y):
    """Узор булата: 0 — тёмное поле (протравленная матрица), 1 — светлые струи карбидов.
    Контуры сильно искривлённого (domain warp) анизотропного шума — «водяной» узор,
    поперечные «колена» с шагом ~16 мм — коленчатый узор, который Аносов считал лучшим."""
    w1 = fbm(x / 60, y / 22, 11, 3)
    w2 = fbm(x / 60 + 5.2, y / 22 + 1.3, 23, 3)
    knee = np.sin(2 * np.pi * (x / 18.0 + 0.6 * w1))            # колена поперёк клинка
    px = x / 34.0 + 1.6 * w1
    py = y / 7.0 + 1.3 * w2 + 0.35 * knee
    F = fbm(px, py, 37, 3, gain=0.42) + 0.10 * knee + y / 40.0
    k = 3.2                                                        # плотность струй
    q = np.abs(((F * k) % 1.0) - 0.5) * 2                          # 1 на гребне контура
    wid = 0.30 + 0.16 * fbm(x / 14, y / 6, 51, 2)                  # толщина струи гуляет — струи ветвятся и рвутся
    lines = ss(1 - wid, 1 - wid + 0.12, q)                         # ЧЁТКИЙ край, без мыла
    # сетка: вторая, мельче и слабее, связывает струи перемычками
    G = fbm(x / 9 + 1.2 * w2, y / 4.5 + 0.8 * w1, 61, 2)
    q2 = np.abs(((G * 1.6) % 1.0) - 0.5) * 2
    net = ss(0.80, 0.92, q2) * 0.45
    b = np.maximum(lines, net * (1 - lines))
    grain = perlin(x * 1.7, y * 1.7, 71) * 0.5 + perlin(x * 4.1, y * 4.1, 72) * 0.5
    return np.clip(b * (0.88 + 0.12 * grain), 0, 1), grain


def _splat(canvas, px, py, r):
    """Нарисовать диск радиуса r (пиксели) в точке (px, py) холста — max-смешение с мягким краем."""
    H, W = canvas.shape
    x0, x1 = int(max(0, px - r - 2)), int(min(W, px + r + 3))
    y0, y1 = int(max(0, py - r - 2)), int(min(H, py + r + 3))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.sqrt((xx + 0.5 - px) ** 2 + (yy + 0.5 - py) ** 2)
    v = np.clip(r + 0.5 - d, 0, 1)
    canvas[y0:y1, x0:x1] = np.maximum(canvas[y0:y1, x0:x1], v)


def ornament(ppm=8):
    """Золотой растительный орнамент для панели у пяты — холст в мм-пространстве (ppm пикс/мм):
    волнистый стебель с завитками-спиралями и листьями-аканфами, как на клинке k1 (Музей истории Златоуста)."""
    W = int((GOLD_X1 - GOLD_X0 + 4) * ppm); H = int(WMAX * ppm)
    c = np.zeros((H, W), np.float32)
    rng = np.random.default_rng(1838)
    L = GOLD_X1 - GOLD_X0 - 10
    yc = 12.5   # ось стебля, мм от обуха
    # стебель
    t = np.linspace(0, 1, 3000)
    sx = 5 + t * L; sy = yc + 4.2 * np.sin(t * 2 * np.pi * 5.0) * (0.6 + 0.4 * t)
    for X, Y, tt in zip(sx, sy, t):
        _splat(c, X * ppm, Y * ppm, (0.55 + 0.35 * (1 - tt)) * ppm)
    # завитки и листья на каждой полуволне
    for k in range(10):
        tk = (k + 0.5) / 10
        X0 = 5 + tk * L; Y0 = yc + 4.2 * np.sin(tk * 2 * np.pi * 5.0) * (0.6 + 0.4 * tk)
        side = 1 if k % 2 == 0 else -1
        R = 4.2 + rng.uniform(-0.4, 0.6)
        # спираль-завиток
        th = np.linspace(0, 2.4 * np.pi, 500)
        rr = R * (1 - th / (2.6 * np.pi))
        cx, cy = X0 + 2.0, Y0 - side * R * 0.9
        for a, r_ in zip(th, rr):
            _splat(c, (cx + r_ * np.cos(a * side + np.pi / 2)) * ppm, (cy + side * r_ * np.sin(a * side + np.pi / 2)) * ppm,
                   (0.25 + 0.30 * r_ / R) * ppm)
        # три листа-аканфа веером
        for j, ang in enumerate((-0.9, -0.2, 0.55)):
            ln = 5.5 + 1.5 * (j == 1)
            base = np.array([X0 - 1.0, Y0])
            dirv = np.array([np.cos(ang + np.pi), side * np.sin(ang + np.pi * 0.5)])
            dirv /= np.linalg.norm(dirv)
            nrm = np.array([-dirv[1], dirv[0]])
            for s in np.linspace(0, 1, 120):
                bend = 1.4 * s * s
                p = base + dirv * ln * s + nrm * bend * side
                _splat(c, p[0] * ppm, p[1] * ppm, (0.15 + 1.25 * np.sin(np.pi * s ** 0.8)) * ppm)
        # ягодка-точка
        _splat(c, (X0 + 5.5) * ppm, (Y0 + side * 5.0) * ppm, 0.9 * ppm)
    # рамка панели (двойная тонкая линия)
    return c


def panel_mask(x, y, w):
    """Воронёная панель у пяты: от обуха до ~0.78 ширины, концы скруглены."""
    top = 1.6; bot = 0.78 * w
    m = ss(GOLD_X0, GOLD_X0 + 0.8, x) * (1 - ss(GOLD_X1 - 8, GOLD_X1, x + 6 * ((y - top) / (bot - top + 1e-6)) ** 2))
    m = m * ss(top, top + 0.4, y) * (1 - ss(bot - 0.4, bot, y))
    return np.clip(m, 0, 1)


def shirina(x):
    """Ширина клинка (мм) в точке x мм от пяты: 35 у пяты → 29 к острию, остриё — четверть эллипса со стороны лезвия.
    35 мм — donklinok.ru; сужение и форма острия — допущение по фото k1/k2."""
    x = np.asarray(x, float)
    w = 35.0 - 6.0 * (x / LB)
    s0 = LB - 70.0
    t = np.clip((x - s0) / 70.0, 0, 1)
    return w * np.sqrt(np.clip(1 - t ** 2, 0, 1)) * (1 - t) ** 0.15 + 0.4 * t


def atlas(N=1024):
    """Атлас клинка N×N: (база RGB linear, шероховатость, высота для нормалей), массивы [v, u] с v вверх (как в Блендере)."""
    j, i = np.mgrid[0:N, 0:N].astype(np.float64)
    u = (i + 0.5) / N; v = (j + 0.5) / N
    row = np.minimum((v * ROWS).astype(int), ROWS - 1)
    vr = v * ROWS - row
    x = row * LSEG + (u - PADU) / (1 - 2 * PADU) * LSEG
    y = (vr - PADV) / (1 - 2 * PADV) * WMAX
    b, grain = uzor(x, y)
    # поле и струи: тёмная протравленная матрица и светлые карбиды
    dark = np.array([0.090, 0.092, 0.098]); light = np.array([0.62, 0.62, 0.60])
    col = dark[None, None, :] * (1 - b[..., None]) + light[None, None, :] * b[..., None]
    rough = 0.46 - 0.24 * b + 0.04 * grain
    h = 0.55 * b + 0.06 * grain
    # гравировка у пяты
    w = shirina(x)
    pm = panel_mask(x, y, w)
    orn = ornament(8)
    oi = np.clip(((x - GOLD_X0 + 2) * 8).astype(int), 0, orn.shape[1] - 1)
    oj = np.clip((y * 8).astype(int), 0, orn.shape[0] - 1)
    g = orn[oj, oi] * pm * ((x > GOLD_X0) & (x < GOLD_X1))
    blue = np.array([0.012, 0.016, 0.028]); gold = np.array([1.0, 0.70, 0.30])
    col = col * (1 - pm[..., None]) + blue[None, None, :] * pm[..., None]
    col = col * (1 - g[..., None]) + gold[None, None, :] * g[..., None]
    rough = rough * (1 - pm) + 0.30 * pm
    rough = rough * (1 - g) + (0.24 + 0.05 * grain) * g
    h = h * (1 - pm) - 0.25 * pm + 0.9 * g
    return col.astype(np.float32), np.clip(rough, 0.05, 1).astype(np.float32), h.astype(np.float32)


def normali(h, sila=3.0):
    gx = np.roll(h, -1, 1) - np.roll(h, 1, 1)
    gy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
    n = np.stack([-gx * sila, -gy * sila, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return (n * 0.5 + 0.5).astype(np.float32)


if __name__ == '__main__':
    import sys
    from PIL import Image
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 1024
    col, r, h = atlas(N)
    srgb = lambda a: np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.clip(a, 0, 1), 1 / 2.4) - 0.055)
    Image.fromarray((np.flipud(srgb(col)) * 255).astype(np.uint8)).save('/tmp/r579/03/_atlas_col.png')
    Image.fromarray((np.flipud(r) * 255).astype(np.uint8)).save('/tmp/r579/03/_atlas_r.png')
    Image.fromarray((np.flipud(normali(h)) * 255).astype(np.uint8)).save('/tmp/r579/03/_atlas_n.png')
    print('ok')
