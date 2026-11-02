

# ======================= Блендер: геометрия, материалы, сцена, снимки, кадры =======================
import bpy, math, sys, os
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '/tmp/r579/03')
from bulat_tex import *   # noqa: узор, атлас, ширина клинка

A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['glb', '/tmp/r579/03/bulat.glb']
MODE = A[0]
HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '/tmp/r579/03'
MM = 0.001

RAZMERY = {
    # donklinok.ru (шашка казачья обр. 1838): клинок 875 мм (офицерская «около 820 мм»), ширина «до 36 мм», рукоять 175 мм,
    #   один широкий дол, раздвоенная головка-«гусёк», прибор ножен: устье, две гайки с кольцами, наконечник.
    # antikvariat.ru/mmg/4024/87453: офицерская шашка обр. 1838 с клеймом «Златоустъ»: общая 97 см, клинок 81 см.
    'klinok': 820,        # мм, длина клинка (donklinok.ru, офицерская)
    'shirina': 35,        # мм у пяты (donklinok.ru, «до 36», офицерская 35)
    'rukoyat': 175,       # мм, рукоять с головкой (donklinok.ru)
    'progib': 40,         # мм, стрела прогиба клинка по хорде — ДОПУЩЕНИЕ (по фото k1; источника на шашку нет)
    'obuh': 7.5,          # мм, толщина обуха у пяты — ДОПУЩЕНИЕ
    'hvostovik': 140,     # мм — ДОПУЩЕНИЕ
    'nozhny': 845,        # мм = клинок + 25 — ДОПУЩЕНИЕ
    'tigel_h': 200, 'tigel_d': 125,   # мм — ДОПУЩЕНИЕ: под загрузку 12 фунтов (≈5 кг) железа (blog.zlatcbs.ru)
    'hlebets_d': 125, 'hlebets_m': 900,  # мм, г — страница дня 03.yaml («около 12,5 см», «около 900 граммов»)
}
SAG = RAZMERY['progib']
R_ARC = (LB * LB / 4 + SAG * SAG) / (2 * SAG)      # радиус дуги обуха, мм
TILT = math.atan2(2 * SAG, LB) * 2 * 0.5 + math.radians(1.0)   # наклон, чтобы хорда клинка лежала почти горизонтально


def spine(s):
    """Точка обуха и нормаль к лезвию (в плоскости XZ, мм), s — мм вдоль обуха от пяты."""
    th = s / R_ARC
    p = Vector((R_ARC * math.sin(th), 0, R_ARC * (1 - math.cos(th))))
    n = Vector((math.sin(th), 0, -math.cos(th)))
    return p, n


def obuh(s):
    """Толщина клинка у обуха, мм: 7,5 у пяты → 3,2 у начала острия → 1 у острия (допущение)."""
    t = s / LB
    return 7.5 - 4.3 * min(1, t / 0.91) - 2.2 * max(0, (t - 0.91) / 0.09)


def polut(s, t):
    """Полутолщина клинка (мм) в точке: t — доля ширины от обуха (0) к лезвию (1). Дол — широкий, как у шашки обр. 1838."""
    T = obuh(s) / 2
    if t < 0.10:
        h = T
    elif t < 0.55:
        h = T * (1 - 0.18 * (t - 0.10) / 0.45)
    else:
        u = (t - 0.55) / 0.45
        h = T * 0.82 * (1 - u) ** 1.15 + 0.12 * u
    # дол: от 45 мм до 0.80 длины, по ширине 0.14–0.42, глубина 30 % полутолщины, края скруглены
    a = float(ss(40, 75, s) * (1 - ss(0.74 * LB, 0.82 * LB, s)))
    c, half = 0.28, 0.14
    d = abs(t - c) / half
    if d < 1 and a > 0:
        h -= a * T * 0.30 * (1 - d * d) ** 0.7
    return max(h, 0.08)


def uv_atlas(x, y):
    row = int(min(ROWS - 1, max(0, x // LSEG)))
    u = PADU + (x - row * LSEG) / LSEG * (1 - 2 * PADU)
    v = (row + PADV + (y / WMAX) * (1 - 2 * PADV)) / ROWS
    return (u, v)


def mesh_obj(name, verts, faces, uvs=None, mats=None, mat_idx=None, smooth=True, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    if uvs is not None:
        uvl = me.uv_layers.new(name='UVMap')
        k = 0
        for poly in me.polygons:
            for li in poly.loop_indices:
                uvl.data[li].uv = uvs[k]; k += 1
    for m in (mats or []):
        me.materials.append(m)
    if mat_idx is not None:
        for poly, mi in zip(me.polygons, mat_idx):
            poly.material_index = mi
    me.validate(); me.update()
    if smooth:
        me.shade_smooth()
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def recenter(ob):
    """Начало координат узла — в центр его рамки (туда цепляется подпись в просмотрщике)."""
    vs = [v.co for v in ob.data.vertices]
    c = Vector((sum(v.x for v in vs), sum(v.y for v in vs), sum(v.z for v in vs))) / len(vs)
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
    hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    c = (lo + hi) / 2
    ob.data.transform(Matrix.Translation(-c))
    ob.location = ob.location + c
    return ob


class Builder:
    """Копилка вершин/граней/UV/материалов одной детали."""
    def __init__(self):
        self.v, self.f, self.uv, self.mi = [], [], [], []

    def grid(self, P, UV, closed_u=False, closed_v=False, mat=0, flip=False):
        """P[i][j] — точки (Vector), UV[i][j] — uv; квады между соседями."""
        n, m = len(P), len(P[0])
        base = len(self.v)
        for row in P:
            self.v.extend(row)
        idx = lambda i, j: base + (i % n) * m + (j % m)
        for i in range(n if closed_u else n - 1):
            for j in range(m if closed_v else m - 1):
                q = [idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)]
                uq = [UV[i % n][j % m], UV[(i + 1) % n][j % m], UV[(i + 1) % n][(j + 1) % m], UV[i % n][(j + 1) % m]]
                if closed_u and i == n - 1:
                    uq[1] = (uq[1][0] + 1, uq[1][1]); uq[2] = (uq[2][0] + 1, uq[2][1])
                if flip:
                    q.reverse(); uq.reverse()
                self.f.append(q); self.uv.extend(uq); self.mi.append(mat)

    def poly(self, pts, uvs, mat=0, flip=False):
        base = len(self.v); self.v.extend(pts)
        q = list(range(base, base + len(pts))); u = list(uvs)
        if flip:
            q.reverse(); u.reverse()
        self.f.append(q); self.uv.extend(u); self.mi.append(mat)

    def obj(self, name, mats, smooth=True, coll=None):
        return mesh_obj(name, [tuple(p) for p in self.v], self.f, self.uv, mats, self.mi, smooth, coll)


# ---------------- материалы ----------------
def img_from(name, arr, srgb, save_dir=None):
    H, W = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, -1)
    if srgb:
        arr = np.where(arr <= 0.0031308, arr * 12.92, 1.055 * np.power(np.clip(arr, 0, 1), 1 / 2.4) - 0.055)
    rgba = np.concatenate([np.clip(arr, 0, 1), np.ones((H, W, 1), np.float32)], -1).astype(np.float32)
    im = bpy.data.images.new(name, W, H, alpha=False)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    im.pixels.foreach_set(rgba.ravel())
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        im.filepath_raw = os.path.join(save_dir, name + '.png'); im.file_format = 'PNG'; im.save()
    else:
        im.pack()
    return im


def mat_pbr(name, base=None, rough=None, metal=None, normal=None, nstr=1.0, col=(0.5, 0.5, 0.5), r=0.5, m=0.0):
    mt = bpy.data.materials.new(name); mt.use_nodes = True
    nt = mt.node_tree; b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = r; b.inputs['Metallic'].default_value = m
    if base is not None:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = base; nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    if rough is not None:   # ORM: G — шероховатость, B — металличность (так glTF-экспортёр пакует metallicRoughness)
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = rough
        sp = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(t.outputs['Color'], sp.inputs['Color'])
        nt.links.new(sp.outputs['Green'], b.inputs['Roughness'])
        if metal:
            nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    if normal is not None:
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = normal
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nstr
        nt.links.new(t.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return mt


def tex_glina(N=512):
    """Тигель: уральская огнеупорная глина с толчёным углём — охра с чёрными крупинками угля, обожжённая."""
    j, i = np.mgrid[0:N, 0:N].astype(np.float64)
    x, y = i / N * 64, j / N * 64
    n1 = fbm(x / 6, y / 6, 101, 4); n2 = perlin(x * 1.3, y * 1.3, 102)
    specks = ss(0.42, 0.50, perlin(x * 2.2, y * 2.2, 103) + 0.35 * perlin(x * 5, y * 5, 104))
    base = np.array([0.42, 0.30, 0.20]) * (0.85 + 0.25 * n1[..., None]) + np.array([0.06, 0.03, 0.0]) * n2[..., None]
    soot = ss(0.1, 0.8, fbm(x / 14, y / 10 + 3, 105, 3)) * 0.65          # копоть горна
    base = base * (1 - soot[..., None]) + np.array([0.03, 0.025, 0.022]) * soot[..., None]
    base = base * (1 - specks[..., None]) + np.array([0.015, 0.014, 0.013]) * specks[..., None]
    rough = 0.82 + 0.1 * n2 - 0.15 * specks
    h = 0.5 * n1 + 0.25 * n2 - 0.3 * specks
    return base.astype(np.float32), rough.astype(np.float32), h.astype(np.float32)


def tex_kozha(N=512):
    """Ножны: чёрная кожа с мелкой мерейкой — шум ячеек."""
    j, i = np.mgrid[0:N, 0:N].astype(np.float64)
    x, y = i / N * 96, j / N * 96
    n = np.abs(perlin(x, y, 201)) + 0.5 * np.abs(perlin(x * 2.1, y * 2.1, 202))
    h = 1 - ss(0.0, 0.35, n)
    base = np.stack([0.018 + 0.010 * h, 0.014 + 0.008 * h, 0.012 + 0.006 * h], -1)
    rough = 0.42 + 0.22 * (1 - h)
    return base.astype(np.float32), rough.astype(np.float32), h.astype(np.float32) * 0.5


def tex_derevo(N=512):
    """Черен рукояти: тёмный рог/морёное дерево — продольные волокна."""
    j, i = np.mgrid[0:N, 0:N].astype(np.float64)
    x, y = i / N * 40, j / N * 40
    f = fbm(x / 1.5, y / 18, 301, 4)
    st = 0.5 + 0.5 * np.sin(f * 14)
    base = np.stack([0.030 + 0.035 * st, 0.018 + 0.020 * st, 0.012 + 0.010 * st], -1)
    rough = 0.38 + 0.15 * st
    return base.astype(np.float32), rough.astype(np.float32), (st * 0.4).astype(np.float32)


def orm(rough, metal):
    H, W = rough.shape
    return np.stack([np.ones((H, W)), rough, np.full((H, W), metal)], -1).astype(np.float32)


def materialy(Nb, save_dir):
    col, rough, h = atlas(Nb)
    M = {}
    M['bulat'] = mat_pbr('bulat', img_from('bulat_base', col, True, save_dir), img_from('bulat_orm', orm(rough, 1.0), False, save_dir),
                         True, img_from('bulat_norm', normali(h, 2.2 * Nb / 1024), False, save_dir), 1.0)
    gb, gr, gh = tex_glina(512)
    M['glina'] = mat_pbr('glina', img_from('glina_base', gb, True, save_dir), img_from('glina_orm', orm(gr, 0.0), False, save_dir),
                         False, img_from('glina_norm', normali(gh, 4.0), False, save_dir), 1.0)
    kb, kr, kh = tex_kozha(512)
    M['kozha'] = mat_pbr('kozha', img_from('kozha_base', kb, True, save_dir), img_from('kozha_orm', orm(kr, 0.0), False, save_dir),
                         False, img_from('kozha_norm', normali(kh, 3.0), False, save_dir), 0.8)
    db, dr, dh = tex_derevo(512)
    M['cheren'] = mat_pbr('cheren', img_from('cheren_base', db, True, save_dir), img_from('cheren_orm', orm(dr, 0.0), False, save_dir),
                          False, img_from('cheren_norm', normali(dh, 2.0), False, save_dir), 0.7)
    M['latun'] = mat_pbr('latun_zoloch', col=(0.95, 0.68, 0.32), r=0.26, m=1.0)       # золочёная латунь прибора
    M['stal_kovka'] = mat_pbr('stal_kovka', col=(0.16, 0.16, 0.17), r=0.55, m=1.0)     # хвостовик: сталь после ковки
    M['okalina'] = mat_pbr('okalina', col=(0.055, 0.050, 0.048), r=0.78, m=0.6)       # корка слитка
    return M


# ---------------- детали ----------------
NS_BL = 300


def klinok(M):
    B = Builder()
    NT = 44
    ts = [0.5 - 0.5 * math.cos(math.pi * k / (NT - 1)) for k in range(NT)]     # гуще у обуха и лезвия
    ss_ = [LB * (k / (NS_BL - 1)) ** 1.0 for k in range(NS_BL)]
    front, back, uvf = [], [], []
    for s in ss_:
        p, n = spine(s); w = float(shirina(s))
        rf, rb, ru = [], [], []
        for t in ts:
            y = t * w; h = polut(s, t)
            q = p + n * y
            rf.append(Vector((q.x, -h, q.z)) * MM); rb.append(Vector((q.x, h, q.z)) * MM)
            ru.append((s, y))
        front.append(rf); back.append(rb); uvf.append(ru)
    # UV по атласу: ряд выбирается по середине квада (шов полос — только в UV, без разрыва нормалей)
    for side, P in ((0, front), (1, back)):
        base = len(B.v)
        for row in P:
            B.v.extend(row)
        m = NT
        for i in range(NS_BL - 1):
            smid = (ss_[i] + ss_[i + 1]) / 2
            row = int(min(ROWS - 1, smid // LSEG))
            for j in range(NT - 1):
                q = [base + i * m + j, base + (i + 1) * m + j, base + (i + 1) * m + j + 1, base + i * m + j + 1]
                cs = [uvf[i][j], uvf[i + 1][j], uvf[i + 1][j + 1], uvf[i][j + 1]]
                uq = []
                for (x, y) in cs:
                    u = PADU + (x - row * LSEG) / LSEG * (1 - 2 * PADU)
                    v = (row + PADV + (y / WMAX) * (1 - 2 * PADV)) / ROWS
                    uq.append((u, v))
                if side == 0:
                    q.reverse(); uq.reverse()
                B.f.append(q); B.uv.extend(uq); B.mi.append(0)
    # обух (плоский, со своими вершинами — острые грани), лезвие, торец пяты
    def strip(j, flip):
        P = [[front[i][j], back[i][j]] for i in range(NS_BL)]
        UV = [[uv_atlas(ss_[i], 0.3), uv_atlas(ss_[i], 0.6)] for i in range(NS_BL)]
        B.grid(P, UV, flip=flip)
    strip(0, False); strip(NT - 1, True)
    B.poly([front[0][j] for j in range(NT)] + [back[0][j] for j in reversed(range(NT))],
           [uv_atlas(1, 1)] * (2 * NT), flip=False)
    return B.obj('klinok', [M['bulat']])


def hvostovik(M):
    B = Builder()
    L = RAZMERY['hvostovik']
    N, NT = 24, 8
    P, UV = [], []
    for k in range(N):
        a = k / (N - 1); x = -L * a
        top = -1.5 - 2.0 * a; bot = -30.0 + 16.0 * a           # сужение к концу (по фото k1 — грубая кованая полоса)
        T = 3.0 - 1.2 * a
        P.append([Vector((x, -T, top)) * MM, Vector((x, -T, bot)) * MM, Vector((x, T, bot)) * MM, Vector((x, T, top)) * MM])
        UV.append([(a, 0), (a, 0.33), (a, 0.66), (a, 1)])
    B.grid(P, UV, closed_v=True, flip=True)
    e = P[-1]; B.poly(e, [(0, 0), (1, 0), (1, 1), (0, 1)])
    return B.obj('hvostovik', [M['stal_kovka']], smooth=False)


def ring_ell(c, ax_u, ax_v, a, b, n=40, pw=2.4, phase=0.0):
    """Сечение-суперэллипс: полуоси a (вдоль ax_u), b (вдоль ax_v)."""
    out = []
    for k in range(n):
        t = 2 * math.pi * k / n + phase
        cu, su = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(cu) ** (2 / pw), cu); y = b * math.copysign(abs(su) ** (2 / pw), su)
        out.append(c + ax_u * x + ax_v * y)
    return out


def loft(B, frames, sec, n=40, mat=0, cap0=False, cap1=False, vscale=1.0):
    """frames: [(центр, ось_u, ось_v, a, b, pw)] — трубка по сечениям; UV u — по окружности, v — по длине (мм)."""
    P, UV = [], []
    L = 0.0
    for i, (c, eu, ev, a, b, pw) in enumerate(frames):
        if i:
            L += (c - frames[i - 1][0]).length
        P.append(ring_ell(c, eu, ev, a, b, n, pw))
        UV.append([(k / n, L / MM / 1000 * vscale) for k in range(n)])
    B.grid(P, UV, closed_v=True, mat=mat)
    if cap0:
        B.poly(P[0], [(0.5, 0.5)] * n, mat=mat, flip=True)
    if cap1:
        B.poly(P[-1], [(0.5, 0.5)] * n, mat=mat)
    return P


def rukoyat(M):
    """Черен 130 мм от пяты назад, слегка выгнут к лезвию, с витой нарезкой; латунная обойма у клинка и две заклёпки."""
    B = Builder()
    L = 130.0
    frames = []
    N = 70
    for k in range(N):
        a = k / (N - 1); x = -L * a
        zc = -16.0 - 7.0 * a * a                                  # ось чуть уходит к лезвию
        hw = 13.5 + 1.8 * math.sin(math.pi * a) + 1.5 * a          # полуширина (по Z)
        ht = 9.0 + 1.6 * math.sin(math.pi * a) + 1.5 * a           # полутолщина (по Y)
        frames.append((Vector((x, 0, zc)) * MM, Vector((0, 0, 1)), Vector((0, 1, 0)), hw * MM, ht * MM, 2.3))
    P = loft(B, frames, None, n=48, mat=0, vscale=1.0)
    # витая нарезка: сдвигаем вершины по нормали синусом по спирали
    for i, ring in enumerate(P):
        a = i / (N - 1)
        c = frames[i][0]
        for k, p in enumerate(ring):
            th = 2 * math.pi * k / len(ring)
            g = 0.45 * MM * math.sin(th * 1 + a * 2 * math.pi * 11) * ss(0.06, 0.12, a) * (1 - ss(0.92, 0.99, a))
            d = p - c; d.x = 0
            if d.length > 0:
                ring[k] = p + d.normalized() * g
    base = len(B.v) - N * 48
    for i, ring in enumerate(P):
        for k, p in enumerate(ring):
            B.v[base + i * 48 + k] = p
    # обойма у клинка (латунь)
    fr2 = []
    for k in range(10):
        a = k / 9; x = 2.0 - 16.0 * a
        bump = 0.9 * math.sin(math.pi * a)
        fr2.append((Vector((x, 0, -16.0)) * MM, Vector((0, 0, 1)), Vector((0, 1, 0)), (15.2 + bump) * MM, (10.4 + bump) * MM, 2.3))
    loft(B, fr2, None, n=48, mat=1, cap0=True)
    # заклёпки
    for xr in (-48.0, -98.0):
        zc = -16.0 - 7.0 * (abs(xr) / L) ** 2
        for sy in (-1, 1):
            fr = []
            for k in range(5):
                a = k / 4
                rr = 3.2 * math.sqrt(max(0.0, 1 - a * a)) + 0.01
                y = sy * (10.2 + 1.6 * math.sin(math.pi * abs(xr) / L) + 1.5 * abs(xr) / L - 0.5 + 1.3 * a)
                fr.append((Vector((xr, y, zc)) * MM, Vector((1, 0, 0)), Vector((0, 0, 1)), rr * MM, rr * MM, 2.0))
            loft(B, fr, None, n=20, mat=1, cap1=True)
    return B.obj('rukoyat', [M['cheren'], M['latun']])


def golovka(M):
    """Раздвоенная головка «гусёк»: контур (мм, в плоскости XZ), выдавлен и скруглён кривой Блендера."""
    pts = [(0, 1.5), (-10, 2.5), (-22, 5.5), (-33, 11.0), (-41, 13.5), (-46, 10.5), (-45.5, 4.0), (-41, -1.0),
           (-36, -4.5), (-37.5, -9.5), (-43, -15.0), (-44, -21.0), (-38, -25.0), (-27, -26.5), (-16, -29.0), (-6, -31.0), (0, -31.5)]
    cu = bpy.data.curves.new('golovka_c', 'CURVE'); cu.dimensions = '2D'; cu.fill_mode = 'BOTH'
    sp = cu.splines.new('BEZIER'); sp.bezier_points.add(len(pts) - 1); sp.use_cyclic_u = True
    for bp, (x, z) in zip(sp.bezier_points, pts):
        bp.co = (x * MM, z * MM, 0); bp.handle_left_type = bp.handle_right_type = 'AUTO'
    cu.extrude = 8.5 * MM; cu.bevel_depth = 3.2 * MM; cu.bevel_resolution = 4; cu.resolution_u = 10
    cu.offset = -3.0 * MM
    ob = bpy.data.objects.new('golovka_tmp', cu); bpy.context.scene.collection.objects.link(ob)
    ob.rotation_euler = (math.pi / 2, 0, 0)   # контур XY → XZ, выдавливание — по Y
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.transform(ob.matrix_world)
    bpy.data.objects.remove(ob); bpy.data.curves.remove(cu)
    me.name = 'golovka'
    # сдвиг: головка стоит в конце черена (x = -130 мм, ось черена z ≈ -23)
    me.transform(Matrix.Translation(Vector((-128.0, 0, -7.5)) * MM))
    me.materials.append(M['latun'])
    for p in me.polygons:
        p.use_smooth = True
    uvl = me.uv_layers.new(name='UVMap')
    for l in me.loops:
        co = me.vertices[l.vertex_index].co; uvl.data[l.index].uv = (co.x * 20, co.z * 20)
    ob = bpy.data.objects.new('golovka', me); bpy.context.scene.collection.objects.link(ob)
    return ob


def nozhny_put(s):
    """Ось ножен: та же дуга, что у клинка, на 17 мм ниже обуха (середина ширины)."""
    p, n = spine(s)
    return p + n * 18.0, n


def nozhny_frames(s0, s1, N, grow=0.0):
    fr = []
    for k in range(N):
        s = s0 + (s1 - s0) * k / (N - 1)
        c, n = nozhny_put(min(s, LB + 25))
        t = Vector((n.z * -1, 0, n.x)) * -1
        a = 22.5 - 5.0 * (s / LB) + grow            # полуширина ножен — допущение (клинок + деревянные щёчки + кожа)
        b = 8.0 - 2.4 * (s / LB) + grow
        fr.append((c * MM, n, Vector((0, 1, 0)), a * MM, b * MM, 2.6))
    return fr


def nozhny(M):
    B = Builder()
    LN = RAZMERY['nozhny']
    loft(B, nozhny_frames(0, LN - 3, 160), None, n=40, mat=0, cap0=True, vscale=4.0)
    # средняя гайка с кольцом (латунь) на 260 мм от устья
    loft(B, nozhny_frames(258, 276, 6, grow=1.2), None, n=40, mat=1)
    c, n = nozhny_put(267)
    tor(B, c + Vector((0, 0, 0)) + n * -26.0, 7.5, 1.5, n, mat=1)
    return B.obj('nozhny', [M['kozha'], M['latun']])


def tor(B, c, R, r, axis_in_plane, mat=1, nu=28, nv=10):
    """Кольцо для портупеи в плоскости XZ."""
    P, UV = [], []
    e1 = Vector((1, 0, 0)); e2 = Vector((0, 0, 1))
    for i in range(nu):
        a = 2 * math.pi * i / nu
        cc = c + (e1 * math.cos(a) + e2 * math.sin(a)) * R
        rr = (e1 * math.cos(a) + e2 * math.sin(a))
        row = []
        for j in range(nv):
            b = 2 * math.pi * j / nv
            row.append((cc + rr * math.cos(b) * r + Vector((0, 1, 0)) * math.sin(b) * r) * MM)
        P.append(row); UV.append([(i / nu, j / nv) for j in range(nv)])
    B.grid(P, UV, closed_u=True, closed_v=True, mat=mat)


def ustye(M):
    B = Builder()
    fr = nozhny_frames(-4, 72, 24, grow=1.3)
    for k, f in enumerate(fr):   # пояски на краях
        a = k / (len(fr) - 1)
        g = 0.9 * (ss(0.0, 0.05, a) * (1 - ss(0.07, 0.12, a)) + ss(0.88, 0.93, a) * (1 - ss(0.95, 1.0, a))) * MM
        fr[k] = (f[0], f[1], f[2], f[3] + g, f[4] + g, f[5])
    loft(B, fr, None, n=40, mat=0, cap0=False)
    c, n = nozhny_put(40)
    tor(B, c + n * -27.0, 7.5, 1.5, n, mat=0)
    # внутренняя «губа» устья — тёмная щель для клинка
    c0, n0 = nozhny_put(-4)
    sl = ring_ell(c0 * MM, n0, Vector((0, 1, 0)), 19.0 * MM, 4.2 * MM, 24, 6.0)
    B.poly([p + Vector((-0.0002, 0, 0)) for p in sl], [(0.5, 0.5)] * 24, mat=1, flip=True)
    return B.obj('ustye', [M['latun'], M['okalina']])


def nakonechnik(M):
    B = Builder()
    LN = RAZMERY['nozhny']
    fr = nozhny_frames(LN - 95, LN - 3, 30, grow=1.3)
    loft(B, fr, None, n=40, mat=0)
    # шарик-«мочка» на конце
    c, n = nozhny_put(LN)
    t = Vector((-n.z, 0, n.x)).normalized()
    if t.x < 0:
        t = -t
    P, UV = [], []
    for i in range(12):
        a = i / 11 * math.pi
        row = []
        for j in range(20):
            b = 2 * math.pi * j / 20
            d = t * math.cos(a) + (n * math.cos(b) * 1.0 + Vector((0, 1, 0)) * math.sin(b) * 0.8) * math.sin(a)
            row.append((c + t * 2.0 + d * 7.5) * MM)
        P.append(row); UV.append([(j / 20, i / 11) for j in range(20)])
    B.grid(P, UV, closed_v=True, mat=0, flip=True)
    return B.obj('nakonechnik', [M['latun']])


def lathe(B, prof, n=64, mat=0, center=Vector((0, 0, 0)), arc=2 * math.pi, closed=True, a0=0.0):
    """Тело вращения по профилю [(r, z)] мм вокруг оси Z."""
    P, UV = [], []
    L = [0.0]
    for k in range(1, len(prof)):
        L.append(L[-1] + math.hypot(prof[k][0] - prof[k - 1][0], prof[k][1] - prof[k - 1][1]))
    cnt = n if closed else n + 1
    for i in range(cnt):
        a = a0 + arc * i / n
        P.append([(center + Vector((r * math.cos(a), r * math.sin(a), z))) * MM for r, z in prof])
        UV.append([(i / n, L[k] / L[-1]) for k in range(len(prof))])
    B.grid(P, UV, closed_u=closed, mat=mat, flip=True)
    return P


def tigel(M):
    """Тигель: высота 200, Ø 125 мм (допущение), стенка 9 мм, дно 16 мм, развальцованный край."""
    H, R0, R1 = 200.0, 62.5, 50.0
    out = []
    for k in range(25):
        a = k / 24
        z = H * a
        r = R1 + (R0 - R1) * a ** 0.8 - 6.0 * (1 - a) ** 6
        out.append((r, z))
    rim = [(R0 + 1.5, H + 1.0), (R0 + 2.0, H + 3.5), (R0 - 1.0, H + 6.0), (R0 - 7.0, H + 5.0), (R0 - 9.0, H + 2.0)]
    inner = []
    for k in range(20):
        a = 1 - k / 19
        z = 16 + (H - 16) * a
        r = (R1 - 9) + (R0 - 9 - (R1 - 9)) * a ** 0.8
        inner.append((r, z))
    bot = [(0.0, -0.01)] + [(R1 - 6.0 - 4 * (1 - k / 4) ** 2, 0.0 + 0.8 * k / 4) for k in range(5)]
    prof = bot + out + rim + inner + [(20, 16.5), (0.01, 17.0)]
    B = Builder()
    lathe(B, prof, n=72, mat=0)
    ob = B.obj('tigel', [M['glina']])
    # кривизна ручной лепки: лёгкая неровность по шуму
    for v in ob.data.vertices:
        co = v.co
        r = math.hypot(co.x, co.y)
        if r > 1e-5:
            dn = 0.9 * MM * float(perlin(np.array(co.x * 60), np.array(co.z * 40 + co.y * 60), 401))
            co.x += co.x / r * dn; co.y += co.y / r * dn
    return ob


def hlebets(M):
    """Слиток-«хлебец» вуца: Ø 125 мм, ~900 г (03.yaml) → объём ~115 см³, средняя толщина ~9,4 мм; разрублен пополам —
    на срезе протравленный узор (тот же атлас булата)."""
    RR = 62.5
    def top(r):
        return 3.0 + 13.5 * (1 - (r / RR) ** 2) ** 0.55
    def bot(r):
        return -3.0 * (1 - (r / RR) ** 2) ** 0.8
    B = Builder()
    NR, NA = 18, 40
    rs = [RR * (k / (NR - 1)) ** 0.8 for k in range(NR)]
    # корка сверху и снизу — полукруг (угол 0..π), со шишками
    for which, fz, flip in (('top', top, False), ('bot', bot, True)):
        P, UV = [], []
        for i in range(NA + 1):
            a = math.pi * i / NA
            row = []
            for r in rs:
                z = fz(r)
                if which == 'top':
                    z += 0.9 * float(fbm(np.array(r * math.cos(a) / 9), np.array(r * math.sin(a) / 9), 501, 3)) * (r / RR + 0.3)
                row.append(Vector((r * math.cos(a), r * math.sin(a), z)) * MM)
            P.append(row); UV.append([(i / NA, k / NR) for k in range(NR)])
        B.grid(P, UV, mat=1, flip=flip)
    # бок
    P, UV = [], []
    for i in range(NA + 1):
        a = math.pi * i / NA
        P.append([Vector((RR * math.cos(a), RR * math.sin(a), bot(RR))) * MM, Vector((RR * math.cos(a), RR * math.sin(a), top(RR))) * MM])
        UV.append([(i / NA, 0), (i / NA, 1)])
    B.grid(P, UV, mat=1)
    # срез по диаметру (плоскость y = 0): полигон по профилю, UV — в атлас (физический масштаб, мм)
    pts, uvs = [], []
    for r in [-x for x in reversed(rs[1:])] + rs:
        z = top(abs(r)); pts.append(Vector((r, 0, z)) * MM); uvs.append(uv_atlas(300 + r, 30 - z))
    for r in reversed([-x for x in reversed(rs[1:])] + rs):
        z = bot(abs(r)); pts.append(Vector((r, 0, z)) * MM); uvs.append(uv_atlas(300 + r, 30 - z))
    # триангулируем полосами между верхом и низом
    n = len(pts) // 2
    for k in range(n - 1):
        q = [pts[k], pts[k + 1], pts[2 * n - 2 - k], pts[2 * n - 1 - k]]
        u = [uvs[k], uvs[k + 1], uvs[2 * n - 2 - k], uvs[2 * n - 1 - k]]
        B.poly(q, u, mat=0, flip=True)
    return B.obj('hlebets', [M['bulat'], M['okalina']])


# ---------------- сборка ----------------
# разборка: смещение каждой детали (м) в осях её родителя — Блендер (x, y, z); в glb пишется в extras уже в осях glTF
RAZBOR = {
    'klinok': (0.09, 0, 0), 'hvostovik': (0.0, 0, 0), 'rukoyat': (-0.11, 0, 0), 'golovka': (-0.22, 0, 0),
    'nozhny': (0.0, 0, -0.10), 'ustye': (-0.13, 0, -0.10), 'nakonechnik': (0.14, 0, -0.06),
    'tigel': (0.0, 0, 0), 'hlebets': (0.0, 0, 0.09),
}


def stroit(Nb, save_dir=None):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    M = materialy(Nb, save_dir)
    sc = bpy.context.scene
    root = bpy.data.objects.new('shashka', None); sc.collection.objects.link(root)
    root.rotation_euler = (0, TILT, 0)
    root.location = (-0.36, 0, 0.0)
    parts = []
    for f in (klinok, hvostovik, rukoyat, golovka, nozhny, ustye, nakonechnik):
        ob = recenter(f(M)); ob.parent = root; parts.append(ob)
    nz = {p.name: p for p in parts}
    for k in ('nozhny', 'ustye', 'nakonechnik'):   # ножны — позади клинка и ниже
        nz[k].location += Vector((0.035, 0.075, -0.075))
    tg = recenter(tigel(M)); tg.location += Vector((0.40, 0.03, -0.215)); parts.append(tg)
    hb = recenter(hlebets(M)); hb.location += Vector((0.24, -0.06, -0.215 + 0.0065)); hb.rotation_euler = (0, 0, math.radians(-160)); parts.append(hb)
    for p in parts:
        p['razborka'] = list(RAZBOR[p.name])
        p['razborka_gltf'] = [RAZBOR[p.name][0], RAZBOR[p.name][2], -RAZBOR[p.name][1]]
        p['doma'] = list(p.location)
    return root, parts


def razobrat(parts, e):
    for p in parts:
        d = Vector(p['razborka']); p.location = Vector(p['doma']) + d * e


# ---------------- сцена ----------------
POL_Z = -0.215


def svet_i_scena(w, h, samples):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.seed = 579                      # фиксированное зерно: кадр детерминирован на любой машине
    sc.cycles.use_animated_seed = False
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.cycles.max_bounces = 8; sc.cycles.glossy_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    # мир: HDRI студии (Poly Haven, CC0) светит и отражается, камера видит тёмный фон
    world = bpy.data.worlds.new('W'); sc.world = world; world.use_nodes = True
    nt = world.node_tree; nt.nodes.clear()
    hdr = os.path.join(HERE, 'studio.hdr')
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(hdr)
    mp = nt.nodes.new('ShaderNodeMapping'); tc = nt.nodes.new('ShaderNodeTexCoord')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(200))
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    bg = nt.nodes.new('ShaderNodeBackground'); bg.inputs['Strength'].default_value = 0.30
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    dark = nt.nodes.new('ShaderNodeBackground'); dark.inputs['Color'].default_value = (0.006, 0.0065, 0.008, 1)
    lp = nt.nodes.new('ShaderNodeLightPath'); mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(bg.outputs['Background'], mix.inputs[1]); nt.links.new(dark.outputs['Background'], mix.inputs[2])
    out = nt.nodes.new('ShaderNodeOutputWorld'); nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    # пол: тёмный, мягкое отражение, к краям уходит в черноту
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0.2, 0, POL_Z))
    fl = bpy.context.object; fl.name = 'pol'
    fm = bpy.data.materials.new('pol'); fm.use_nodes = True
    b = fm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.012, 0.012, 0.014, 1); b.inputs['Roughness'].default_value = 0.40
    b.inputs['Specular IOR Level'].default_value = 0.3
    fl.data.materials.append(fm)

    def area(name, loc, tgt, size, size_y, energy, col, spread=60):
        ld = bpy.data.lights.new(name, 'AREA'); ld.shape = 'RECTANGLE'
        ld.size, ld.size_y, ld.energy, ld.color = size, size_y, energy, col
        ld.spread = math.radians(spread)
        ob = bpy.data.objects.new(name, ld); sc.collection.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        return ob
    c = (0.2, 0, -0.05)
    area('softboks_pered', (0.25, -2.2, 0.9), c, 2.6, 1.2, 50, (1.0, 0.97, 0.92), 80)   # отражается в плоскости клинка
    area('verh', (0.2, 0.1, 1.4), c, 1.6, 0.6, 25, (1.0, 0.98, 0.95))
    area('kontr_levyj', (-1.3, 1.2, 0.5), c, 1.4, 0.25, 60, (0.80, 0.88, 1.0), 45)
    area('kontr_pravyj', (1.6, 1.0, 0.35), c, 1.4, 0.25, 50, (1.0, 0.86, 0.70), 45)
    cam_d = bpy.data.cameras.new('kamera'); cam_d.lens = 50; cam_d.clip_start = 0.01; cam_d.clip_end = 50
    cam = bpy.data.objects.new('kamera', cam_d); sc.collection.objects.link(cam); sc.camera = cam
    return cam


def navesti(cam, pos, tgt, lens=50):
    cam.location = pos
    cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens


SNIMKI = [  # имя, камера, цель, объектив, разборка 0..1
    ('geroj', (0.62, -1.55, 0.30), (0.17, 0, -0.07), 40, 0.0),
    ('razborka', (0.30, -1.85, 0.42), (0.14, 0, -0.08), 38, 1.0),
    ('uzor-krupno', (0.30, -0.38, 0.06), (0.24, 0, 0.0), 50, 0.0),
    ('pyata-zoloto', (-0.18, -0.42, 0.10), (-0.20, 0, -0.01), 50, 0.0),
]

DUR, FPS = 10.0, 24
CENTR = Vector((0.15, 0.0, -0.07))


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * x * (x * (x * 6 - 15) + 10)


def razbor_t(t):
    """0–2 с собрано, 2–4 разлёт, 4–6,5 разобрано, 6,5–8,5 сборка, 8,5–10 собрано."""
    if t < 2.0:
        return 0.0
    if t < 4.0:
        return ease((t - 2.0) / 2.0)
    if t < 6.5:
        return 1.0
    if t < 8.5:
        return 1.0 - ease((t - 6.5) / 2.0)
    return 0.0


def oblet(t):
    """Облёт полукругом спереди: от левого-верхнего ракурса к правому, дальше на разобранной фазе."""
    u = t / DUR
    az = math.radians(-118 + 56 * (0.5 - 0.5 * math.cos(math.pi * u)))     # азимут камеры вокруг центра
    e = razbor_t(t)
    dist = 1.85 + 0.40 * e
    el = math.radians(16 + 6 * math.sin(math.pi * u))
    pos = CENTR + Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * dist
    return pos, CENTR + Vector((0, 0, 0.01 * e)), 42


def main():
    if MODE == 'tekstury':
        return
    Nb = 1024 if MODE == 'glb' else int(os.environ.get('BULAT_TEX', '2048'))
    if MODE == 'glb':
        out = A[1]
        tdir = os.path.join(os.path.dirname(os.path.abspath(out)), 'tex')
        root, parts = stroit(Nb, tdir)
        bpy.ops.object.select_all(action='DESELECT')
        for p in parts + [root]:
            p.select_set(True)
        for p in parts:   # для glb — только смещение в осях glTF
            del p['razborka']; del p['doma']
            p['nazvanie_uzla'] = p.name
        bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', use_selection=True, export_extras=True,
                                  export_image_format='AUTO', export_apply=True, export_yup=True, export_tangents=False)
        tri = 0
        for p in parts:
            p.data.calc_loop_triangles(); tri += len(p.data.loop_triangles)
        print('GLB', out, os.path.getsize(out), 'байт, треугольников', tri)
        return
    root, parts = stroit(Nb)
    snimki_w = (MODE == 'snimki' and len(A) >= 5) or (MODE == 'kadry' and len(A) >= 7)
    w, h, smp = (int(A[-3]), int(A[-2]), int(A[-1])) if snimki_w else (1920, 1080, 64)
    cam = svet_i_scena(w, h, smp)
    sc = bpy.context.scene
    if MODE == 'snimki':
        d = A[1]; os.makedirs(d, exist_ok=True)
        only = os.environ.get('ONLY')
        for name, pos, tgt, lens, e in SNIMKI:
            if only and only not in name:
                continue
            razobrat(parts, e)
            navesti(cam, pos, tgt, lens)
            sc.render.filepath = os.path.join(d, f'{name}.png')
            bpy.ops.render.render(write_still=True)
    elif MODE == 'kadry':
        d, a, b = A[1], int(A[2]), int(A[3]); os.makedirs(d, exist_ok=True)
        for f in range(a, b + 1):
            t = f / FPS
            razobrat(parts, razbor_t(t))
            pos, tgt, lens = oblet(t)
            navesti(cam, pos, tgt, lens)
            sc.render.filepath = os.path.join(d, f'f{f:05d}.png')
            bpy.ops.render.render(write_still=True)


main()
