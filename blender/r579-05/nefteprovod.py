# r579-05: первый в мире расчётный нефтепровод В. Г. Шухова Балаханы — Чёрный город (1878) кодом в Блендере.
# Музейный макет-разрез: паровой насос прямого действия → нитка трёхдюймовой трубы на муфтах, участок в разрезе с нефтью.
# Блендер 4.2 без окна (интерфейс режимов — как у k278.py, r570):
#   ~/opt/blender-run.sh -t 4 --python nefteprovod.py -- glb    <выход.glb>
#   ~/opt/blender-run.sh -t 4 --python nefteprovod.py -- snimki <папка> [ширина высота сэмплы]
#   ~/opt/blender-run.sh -t 4 --python nefteprovod.py -- kadry  <папка> <с> <по> [ширина высота сэмплы]
# kadry: облёт 10 с × 24 к/с = кадры 0…239, имена f00000.png…; каждый кадр — чистая функция номера кадра
# (сцена строится заново, шум Cycles с постоянным seed), поэтому диапазоны можно резать по разным машинам.
#
# РАЗМЕРЫ (м) и откуда. Всё, чего нет в источниках, помечено «допущение».
#   Ø трубы 3″ = 76,2 мм — ourbaku.com «Первый Российский нефтепровод Балаханы-Черный город»; azerhistory.com/?p=8562; 05.yaml
#   длина нитки ≈10 км (8,5 версты) — azerhistory.com/?p=8562; 05.yaml; «Наука и жизнь» (nkj.ru/archive/articles/23482) — 11 км
#   80 000 пудов в сутки, паровой насос — ourbaku.com; azerhistory.com/?p=8562; 05.yaml
#   стыки — «муфтами американского образца с конической нарезкой» — az.sputniknews.ru/20230829/…-458134774.html
#   насосы паровые, американские — там же. Вортингтон (дуплекс прямого действия) — ДОПУЩЕНИЕ по англоязычным хроникам,
#     русского подтверждения именно для 1878 г. не найдено; размеры насоса 14″×8½″×10″ — ДОПУЩЕНИЕ (типовой ряд).
#   стенка 5,5 мм (наружный Ø 88,9 мм, как у трёхдюймовой американской трубы) — ДОПУЩЕНИЕ
#   звено 6,1 м (20 футов), муфта Ø108 × 160 мм, 8 ниток на дюйм — ДОПУЩЕНИЕ
#   укладка на деревянных опорах над землёй — ДОПУЩЕНИЕ (в источниках не сказано; в макете — чтобы трубу было видно)
import bpy, bmesh, math, sys, os
import numpy as np
from mathutils import Vector, Matrix
from collections import defaultdict

A = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else ['glb', '/tmp/r579/05/nefteprovod-raw.glb']
MODE = A[0]
DIR = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(DIR, 'tex'); os.makedirs(TEX, exist_ok=True)
PH = TEX + '/'   # дерево (Poly Haven CC0) скопировано в tex/
HDR = os.path.join(DIR, 'studio.hdr')
TAU = math.tau

RAZMERY = {
    'D_VN': 0.0762,      # внутренний Ø трубы, 3″ (источники выше)
    'D_NAR': 0.0889,     # наружный Ø — ДОПУЩЕНИЕ (стенка 5,5 мм)
    'ZVENO': 6.1,        # длина звена — ДОПУЩЕНИЕ
    'MUFTA_D': 0.108, 'MUFTA_L': 0.16,   # муфта — ДОПУЩЕНИЕ
    'SHAG_REZBY': 0.0254 / 8,            # 8 ниток на дюйм — ДОПУЩЕНИЕ
    'L_REZBY': 0.07,                     # длина нарезки — ДОПУЩЕНИЕ
    'PAR_D': 0.356, 'NEFT_D': 0.216, 'HOD': 0.254,   # насос 14″×8½″×10″ — ДОПУЩЕНИЕ
}
RO, RI = RAZMERY['D_NAR'] / 2, RAZMERY['D_VN'] / 2
ZT = 0.55                   # ось нитки над землёй (на опорах) — допущение
X_PUSK = 1.05               # фланец начала нитки у насоса
X_MUFTA = 2.6               # разборная муфта
X_RZ0, X_RZ1 = 3.25, 5.25   # участок в разрезе
X_KON = 13.9                # конец нитки в glb (в кадрах — до горизонта)
ZO = 0.75                   # оси цилиндров насоса
YC = 0.32                   # два цилиндра дуплекса: y = ±YC

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

# ── текстуры: периодический шум через БПФ (бесшовно) ────────────────────────────────────────────────────
rng = np.random.default_rng(1878)
def shum(n, beta=2.0, aniz=(1.0, 1.0)):
    w = rng.standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None] * aniz[0]; fx = np.fft.fftfreq(n)[None, :] * aniz[1]
    f = np.sqrt(fx * fx + fy * fy); f[0, 0] = 1
    s = np.real(np.fft.ifft2(np.fft.fft2(w) / f ** (beta / 2 + 0.5)))
    s -= s.min(); return s / s.max()
def ss(a, b, x): t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
def normal_iz(h, k):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * k; dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * k
    n = np.dstack([-dx, -dy, np.ones_like(h)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5
def kartinka(imya, rgb, noncolor=False):
    h, w = rgb.shape[:2]
    im = bpy.data.images.new(imya, w, h, alpha=False)
    px = np.ones((h, w, 4), np.float32); px[..., :3] = np.clip(rgb, 0, 1)
    im.pixels.foreach_set(px.ravel())
    put = os.path.join(TEX, imya + '.png'); im.filepath_raw = put; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)
    im = bpy.data.images.load(put)
    if noncolor: im.colorspace_settings.name = 'Non-Color'
    return im
def lin(c): return np.power(np.asarray(c, np.float32), 1.0)   # цвета ниже заданы в sRGB-пространстве картинки

def tex_stal(n=1024):     # сталь трубы: прокатная окалина + пятна ржавчины + питтинг
    a, b, c = shum(n, 2.2), shum(n, 3.0), shum(n, 1.2)
    rzh = ss(0.58, 0.75, a * 0.7 + c * 0.3)
    okal = np.array([0.20, 0.205, 0.215]) * (0.75 + 0.5 * b[..., None])
    rcol = np.array([0.42, 0.20, 0.08]) * (0.6 + 0.6 * c[..., None]) + np.array([0.1, 0.03, 0]) * a[..., None]
    col = okal * (1 - rzh[..., None]) + rcol * rzh[..., None]
    rough = 0.38 + 0.12 * b + 0.42 * rzh; metal = 0.85 * (1 - rzh) + 0.05
    h = 0.6 * b + 1.2 * rzh * c + 0.25 * (c > 0.82)
    return col, np.dstack([np.ones_like(h), rough, metal]), normal_iz(h, 3.0)
def tex_kraska(n=1024):   # чугун под тёмно-зелёной краской: разводы, мелкие сколы до металла, литейное зерно
    a, b, g = shum(n, 2.0), shum(n, 2.8), shum(n, 0.4)
    skol = ss(0.80, 0.86, a * 0.6 + g * 0.4)
    kr = np.array([0.075, 0.16, 0.115]) * (0.8 + 0.35 * b[..., None])
    zhel = np.array([0.22, 0.21, 0.20])
    col = kr * (1 - skol[..., None]) + zhel * skol[..., None]
    rough = 0.34 + 0.18 * b + 0.15 * skol; metal = 0.9 * skol
    return col, np.dstack([np.ones_like(a), rough, metal]), normal_iz(0.25 * g + 0.3 * b + 0.6 * skol, 2.0)
def tex_pesok(n=1024):    # апшеронский песок с нефтяными пятнами
    a, b, g = shum(n, 2.4), shum(n, 1.0), shum(n, 3.2)
    ryab = 0.5 + 0.5 * np.sin(np.linspace(0, TAU * 24, n)[None, :] + 6 * a)
    col = np.array([0.56, 0.45, 0.31]) * (0.78 + 0.3 * g[..., None] + 0.08 * b[..., None])
    pyat = ss(0.84, 0.9, a)[..., None]
    col = col * (1 - 0.85 * pyat)
    rough = 0.92 - 0.12 * pyat[..., 0]
    return col, np.dstack([np.ones_like(a), rough, np.zeros_like(a)]), normal_iz(0.5 * b + 0.25 * ryab * g + 0.6 * a, 2.5)
def tex_neft(n=512):      # нефть: тёмный глянец, продольные бурые струи (u — по кругу, v — вдоль оси)
    s = shum(n, 2.6, aniz=(0.08, 1.0))
    col = np.array([0.020, 0.013, 0.008])[None, None, :] + np.array([0.11, 0.05, 0.015])[None, None, :] * ss(0.55, 0.95, s)[..., None]
    return col
def tex_ciferblat(n=512): # манометр: слоновая кость, деления по дуге 270°, красная черта
    y, x = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1; r = np.hypot(x, y); a = np.degrees(np.arctan2(x, -y)) % 360
    col = np.ones((n, n, 3)) * np.array([0.86, 0.82, 0.70])
    v = (a >= 45) & (a <= 315); u = (a - 45) / 270 * 50
    melk = v & (r > 0.70) & (r < 0.80) & (np.abs(u - np.round(u)) < 0.07)
    kr = v & (r > 0.62) & (r < 0.82) & (np.abs(u / 5 - np.round(u / 5)) < 0.03)
    col[melk | kr] = (0.05, 0.05, 0.05)
    col[(a > 270) & (a <= 315) & (r > 0.82) & (r < 0.88)] = (0.6, 0.05, 0.03)
    col[(r > 0.93)] = (0.08, 0.07, 0.06)
    return col

# ── материалы ─────────────────────────────────────────────────────────────────────────────────────────
def pbsdf(imya):
    m = bpy.data.materials.new(imya); m.use_nodes = True
    return m, m.node_tree.nodes['Principled BSDF'], m.node_tree
def mat(imya, cvet, metal, sher, coat=0.0):
    m, b, _ = pbsdf(imya)
    b.inputs['Base Color'].default_value = (*cvet, 1); b.inputs['Metallic'].default_value = metal
    b.inputs['Roughness'].default_value = sher
    if coat: b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = 0.02
    return m
def mat_tex(imya, col_img, orm_img=None, nor_img=None, nor_sila=1.0, rough_img=None, coat=0.0, sher=0.5):
    m, b, t = pbsdf(imya); N, L = t.nodes, t.links
    tc = N.new('ShaderNodeTexImage'); tc.image = col_img; L.new(tc.outputs['Color'], b.inputs['Base Color'])
    if orm_img:
        to = N.new('ShaderNodeTexImage'); to.image = orm_img
        sp = N.new('ShaderNodeSeparateColor'); L.new(to.outputs['Color'], sp.inputs['Color'])
        L.new(sp.outputs['Green'], b.inputs['Roughness']); L.new(sp.outputs['Blue'], b.inputs['Metallic'])
    elif rough_img:
        tr = N.new('ShaderNodeTexImage'); tr.image = rough_img; L.new(tr.outputs['Color'], b.inputs['Roughness'])
        b.inputs['Metallic'].default_value = 0.0
    else:
        b.inputs['Roughness'].default_value = sher; b.inputs['Metallic'].default_value = 0.0
    if nor_img:
        tn = N.new('ShaderNodeTexImage'); tn.image = nor_img
        nm = N.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = nor_sila
        L.new(tn.outputs['Color'], nm.inputs['Color']); L.new(nm.outputs['Normal'], b.inputs['Normal'])
    if coat: b.inputs['Coat Weight'].default_value = coat; b.inputs['Coat Roughness'].default_value = 0.03
    return m

c, o, nrm = tex_stal(); st = [kartinka('stal-cvet', c), kartinka('stal-orm', o, True), kartinka('stal-normal', nrm, True)]
c, o, nrm = tex_kraska(); kr = [kartinka('kraska-cvet', c), kartinka('kraska-orm', o, True), kartinka('kraska-normal', nrm, True)]
c, o, nrm = tex_pesok(); ps = [kartinka('pesok-cvet', c), kartinka('pesok-orm', o, True), kartinka('pesok-normal', nrm, True)]
img_neft = kartinka('neft-cvet', tex_neft()); img_cif = kartinka('ciferblat', tex_ciferblat())
def jpg(p, nc=False):
    im = bpy.data.images.load(PH + p)
    if nc: im.colorspace_settings.name = 'Non-Color'
    return im
M = {
    'stal':   mat_tex('stal-truby', st[0], st[1], st[2], 1.0),                       # труба: окалина, ржавчина
    'mufta':  mat_tex('stal-mufty', st[0], st[1], st[2], 0.6),
    'kraska': mat_tex('chugun-kraska', kr[0], kr[1], kr[2], 0.8),                    # чугун под краской
    'pesok':  mat_tex('pesok', ps[0], ps[1], ps[2], 1.0),
    'kamen':  mat_tex('kamen-fundament', ps[0], ps[1], ps[2], 1.6),
    'derevo': mat_tex('derevo', jpg('fine_grained_wood_Diffuse.jpg'), None, jpg('fine_grained_wood_nor_gl.jpg', True), 1.0,
                      rough_img=jpg('fine_grained_wood_Rough.jpg', True)),
    'neft':   mat_tex('neft', img_neft, None, None, sher=0.04, coat=1.0),           # нефть — тёмный глянец
    'cifer':  mat_tex('ciferblat', img_cif, None, None, sher=0.35),
    'latun':  mat('latun', (0.80, 0.58, 0.26), 1.0, 0.24),
    'med':    mat('med', (0.86, 0.48, 0.32), 1.0, 0.30),
    'blesk':  mat('stal-shlif', (0.78, 0.78, 0.77), 1.0, 0.16),                       # шлифованные штоки
    'temn':   mat('stal-temnaya', (0.05, 0.05, 0.055), 0.8, 0.4),
    'srez':   mat('srez-krasnyj', (0.62, 0.04, 0.025), 0.0, 0.42),                     # плоскость разреза, как в музейных макетах
    'steklo': mat('steklo', (0.9, 0.9, 0.9), 0.0, 0.02),
}
for k in ('pesok', 'kamen'):
    b = M[k].node_tree.nodes['Principled BSDF']
M['kamen'].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.8, 0.7, 0.6, 1)
gl = M['steklo'].node_tree.nodes['Principled BSDF']; gl.inputs['Alpha'].default_value = 0.12
M['steklo'].blend_method = 'BLEND'

# ── построители ───────────────────────────────────────────────────────────────────────────────────────
def mesh_obj(imya, verts, faces, uvs, material, rodit, smooth=True):
    me = bpy.data.meshes.new(imya); me.from_pydata(verts, [], faces); me.validate()
    if uvs is not None:
        ul = me.uv_layers.new(name='UV')
        for p in me.polygons:
            for li, vi in zip(p.loop_indices, p.vertices): ul.data[li].uv = uvs[vi]
    for p in me.polygons: p.use_smooth = smooth
    me.materials.append(material)
    ob = bpy.data.objects.new(imya, me); sc.collection.objects.link(ob); ob.parent = rodit
    return ob

def osi(p, d):
    """Матрица: локальная Z → направление d, начало в p."""
    d = Vector(d).normalized()
    return Matrix.Translation(Vector(p)) @ Vector((0, 0, 1)).rotation_difference(d).to_matrix().to_4x4()

def lathe(imya, prof, material, rodit, seg=48, tile=0.5, at=Matrix.Identity(4), a0=0.0, a1=TAU, phase=0.0):
    """Тело вращения вокруг локальной Z. prof — [(r, z), …]; None — излом. a0..a1 — дуга (для разреза)."""
    polosy, cur = [], []
    prof = list(prof)
    while prof and prof[0] is None: prof = prof[1:]
    while prof and prof[-1] is None: prof = prof[:-1]
    for p in prof:
        if p is None: polosy.append(cur); cur = [cur[-1]]
        else: cur.append(p)
    polosy.append(cur)
    rmax = max(p[0] for p in prof if p); nu = max(1, round(TAU * rmax / tile))
    verts, faces, uvs = [], [], []
    for pol in polosy:
        if len(pol) < 2: continue
        base = len(verts); s = 0.0; vv = [0.0]
        for j in range(1, len(pol)): s += math.hypot(pol[j][0] - pol[j - 1][0], pol[j][1] - pol[j - 1][1]); vv.append(s)
        for j, (r, z) in enumerate(pol):
            for i in range(seg + 1):
                a = a0 + (a1 - a0) * i / seg + phase
                verts.append(tuple(at @ Vector((r * math.cos(a), r * math.sin(a), z))))
                uvs.append((nu * (a1 - a0) / TAU * i / seg, (pol[0][1] + vv[j]) / tile))
        for j in range(len(pol) - 1):
            for i in range(seg):
                a, b = base + j * (seg + 1) + i, base + (j + 1) * (seg + 1) + i
                faces.append((a, a + 1, b + 1, b))
    return mesh_obj(imya, verts, faces, uvs, material, rodit)

def box(imya, size, centr, material, rodit, fask=0.01, rot=None, tile=0.6):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if fask > 0: bmesh.ops.bevel(bm, geom=list(bm.edges), offset=fask, segments=2, profile=0.5, affect='EDGES')
    T = Matrix.Translation(Vector(centr)) @ (rot if rot else Matrix.Identity(4))
    bmesh.ops.transform(bm, matrix=T, verts=bm.verts)
    me = bpy.data.meshes.new(imya); bm.to_mesh(me); bm.free()
    uv = me.uv_layers.new(name='UV')
    for p in me.polygons:
        n = p.normal; ax = max(range(3), key=lambda k: abs(n[k])); u_, v_ = [k for k in range(3) if k != ax]
        for li, vi in zip(p.loop_indices, p.vertices):
            v = me.vertices[vi].co; uv.data[li].uv = (v[u_] / tile, v[v_] / tile)
    for p in me.polygons: p.use_smooth = True
    me.materials.append(material)
    ob = bpy.data.objects.new(imya, me); sc.collection.objects.link(ob); ob.parent = rodit
    return ob

def sterzhen(imya, p1, p2, r, material, rodit, seg=16, fask=0.0):
    p1, p2 = Vector(p1), Vector(p2); L = (p2 - p1).length
    pr = [(r - fask, 0), (r, fask), (r, L - fask), (r - fask, L)] if fask else [(r, 0), (r, L)]
    pr = [(0, 0)] + pr + [(0, L)]
    return lathe(imya, pr, material, rodit, seg=seg, at=osi(p1, p2 - p1), tile=0.2)

def bolty(imya, centr, napr, R, n, s, material, rodit, h=None, faza=0.0):
    """Кольцо шестигранных головок болтов вокруг оси napr на радиусе R (на плоскости фланца)."""
    h = h or s * 0.7; at0 = osi(centr, napr)
    for i in range(n):
        a = TAU * (i + 0.5) / n + faza
        p = at0 @ Vector((R * math.cos(a), R * math.sin(a), 0))
        lathe(imya, [(0, 0), (s, 0), (s, h * 0.8), (s * 0.75, h), (0, h * 1.05)], material, rodit, seg=6,
              at=osi(p, napr), tile=0.1, phase=math.pi / 6)

def flanec(imya, p, napr, r_in, r_out, t, material, rodit, n_bolt=8, seg=48):
    at = osi(p, napr); f = min(0.006, t / 4)
    lathe(imya, [(r_in, 0), (r_out - f, 0), (r_out, f), (r_out, t - f), (r_out - f, t), (r_in, t)], material, rodit, seg=seg, at=at, tile=0.3)
    if n_bolt: bolty(imya + '-bolt', at @ Vector((0, 0, t)), napr, (r_in + r_out) / 2 + 0.004, n_bolt, (r_out - r_in) * 0.22, M['temn'], rodit)

def tor(imya, R, r, at, material, rodit, seg=40, k=12):
    pr = [(R + r * math.cos(TAU * j / k), r * math.sin(TAU * j / k)) for j in range(k + 1)]
    return lathe(imya, pr, material, rodit, seg=seg, at=at, tile=0.2)

UZLY = {}
def uzel(imya, razbor=(0, 0, 0), metka=(0, 0, 0.1), rodit=None):
    e = bpy.data.objects.new(imya, None); sc.collection.objects.link(e); e.parent = rodit or KOREN
    e['razbor'] = [razbor[0], razbor[2], -razbor[1]]      # смещение разборки в осях glTF (Y вверх)
    e['metka'] = [metka[0], metka[2], -metka[1]]          # точка подписи относительно узла, оси glTF
    e['razbor_z'] = list(razbor)
    UZLY[imya] = e
    return e
KOREN = bpy.data.objects.new('nefteprovod-1878', None); sc.collection.objects.link(KOREN)

# ── фундамент и рама ──────────────────────────────────────────────────────────────────────────────────
fund = uzel('fundament', metka=(-0.2, -0.75, 0.18))
for i, x in enumerate(np.linspace(-1.55, 1.05, 5)):            # два ряда тёсаного камня
    box('fund', (0.62, 1.55, 0.13), (x, 0, 0.065), M['kamen'], fund, fask=0.018, tile=1.2)
for i, x in enumerate(np.linspace(-1.25, 0.75, 4)):
    box('fund', (0.62, 1.45, 0.12), (x, 0, 0.19), M['kamen'], fund, fask=0.018, tile=1.2)

rama = uzel('rama', razbor=(0, 0, -0.02), metka=(-0.35, -0.55, 0.42))
box('rama-plita', (2.55, 1.18, 0.07), (-0.35, 0, 0.285), M['kraska'], rama, fask=0.02)
box('rama-poyas', (2.45, 1.08, 0.07), (-0.35, 0, 0.345), M['kraska'], rama, fask=0.025)
for x in np.linspace(-1.5, 0.8, 6):                                  # фундаментные болты
    for s in (-1, 1):
        bolty('rama-bolt', (x, s * 0.56, 0.32), (0, 0, 1), 0.0, 1, 0.022, M['temn'], rama)
for s in (-1, 1):                                                   # литые станины-«ярма» между паровой и нефтяной частью
    y = s * YC
    box('rama-yarmo', (1.02, 0.09, 0.07), (-0.41, y + 0.13, ZO + 0.15), M['kraska'], rama, fask=0.02)
    box('rama-yarmo', (1.02, 0.09, 0.07), (-0.41, y - 0.13, ZO + 0.15), M['kraska'], rama, fask=0.02)
    box('rama-yarmo', (1.02, 0.30, 0.06), (-0.41, y, ZO - 0.2), M['kraska'], rama, fask=0.02)
    for x in (-0.86, 0.05):
        box('rama-stoyka', (0.08, 0.32, ZO - 0.38), (x, y, (0.38 + ZO) / 2 + 0.0), M['kraska'], rama, fask=0.02)
    box('rama-napr', (0.5, 0.24, 0.025), (-0.41, y, ZO - 0.155), M['blesk'], rama, fask=0.004)   # направляющая ползуна

# ── паровые цилиндры (2 шт., дуплекс) ─────────────────────────────────────────────────────────────────
par = uzel('nasos-parovoy-cilindr', razbor=(-0.85, 0, 0.35), metka=(-1.2, -0.3, 1.25))
X0, X1 = -1.50, -0.90; RP = RAZMERY['PAR_D'] / 2 + 0.04
for s in (-1, 1):
    y = s * YC; at = osi((X0, y, ZO), (1, 0, 0)); L = X1 - X0
    lathe('par-korpus', [(0, -0.04), (RP - 0.05, -0.04), (RP - 0.02, -0.02), None, (RP + 0.03, -0.02), (RP + 0.03, 0.03), None,
                         (RP - 0.005, 0.03), (RP - 0.005, L - 0.03), None, (RP + 0.03, L - 0.03), (RP + 0.03, L + 0.01), None, (RP - 0.02, L + 0.01)],
          M['kraska'], par, seg=64, at=at)
    for z in (0.12, L - 0.12):                                     # латунные бандажи обшивки
        lathe('par-bandazh', [(RP + 0.002, z - 0.012), (RP + 0.008, z - 0.008), (RP + 0.008, z + 0.008), (RP + 0.002, z + 0.012)], M['latun'], par, seg=64, at=at)
    lathe('par-kryshka', [(0, -0.075), (0.09, -0.07), (0.12, -0.05), (RP - 0.05, -0.04)], M['kraska'], par, seg=48, at=at)
    lathe('par-kryshka-gaika', [(0, -0.095), (0.045, -0.092), (0.045, -0.07)], M['latun'], par, seg=6, at=at)
    bolty('par-bolt', (X0 - 0.02, y, ZO), (-1, 0, 0), RP + 0.012, 12, 0.016, M['temn'], par)
    bolty('par-bolt', (X1 + 0.01, y, ZO), (1, 0, 0), RP + 0.012, 12, 0.016, M['temn'], par)
    lathe('par-salnik', [(0.05, 0), (0.07, 0), (0.07, 0.05), (0.045, 0.06), (0.04, 0.09)], M['latun'], par, seg=32, at=osi((X1 + 0.01, y, ZO), (1, 0, 0)))
    # золотниковая коробка сверху, крышка на болтах
    box('par-zolotnik', (0.42, 0.24, 0.13), ((X0 + X1) / 2, y, ZO + RP + 0.06), M['kraska'], par, fask=0.025)
    box('par-zolotnik-kryshka', (0.46, 0.28, 0.035), ((X0 + X1) / 2, y, ZO + RP + 0.14), M['kraska'], par, fask=0.012)
    for x in np.linspace(X0 + 0.07, X1 - 0.07, 4):
        for yy in (y - 0.115, y + 0.115):
            bolty('par-bolt', (x, yy, ZO + RP + 0.157), (0, 0, 1), 0.0, 1, 0.012, M['temn'], par)
    # паровпуск: медная труба с латунным вентилем-штурвалом
    xp = (X0 + X1) / 2 - 0.08
    sterzhen('par-vpusk', (xp, y, ZO + RP + 0.16), (xp, y, ZO + RP + 0.36), 0.028, M['med'], par)
    flanec('par-vpusk-fl', (xp, y, ZO + RP + 0.155), (0, 0, 1), 0.028, 0.06, 0.018, M['latun'], par, n_bolt=4)
    lathe('par-ventil', [(0, -0.05), (0.05, -0.05), (0.06, 0), (0.05, 0.05), (0, 0.05)], M['latun'], par, seg=32, at=osi((xp, y, ZO + RP + 0.40), (0, 1, 0)))
    sterzhen('par-ventil-shpindel', (xp, y, ZO + RP + 0.44), (xp, y, ZO + RP + 0.55), 0.008, M['blesk'], par)
    tor('par-shturval', 0.075, 0.008, osi((xp, y, ZO + RP + 0.55), (0, 0, 1)), M['latun'], par)
    for k in range(4):
        a = TAU * k / 4
        sterzhen('par-shturval-spica', (xp, y, ZO + RP + 0.55), (xp + 0.075 * math.cos(a), y + 0.075 * math.sin(a), ZO + RP + 0.55), 0.006, M['latun'], par, seg=8)
sterzhen('par-magistral', (X0 + 0.22, -YC, ZO + RP + 0.40), (X0 + 0.22, YC, ZO + RP + 0.40), 0.03, M['med'], par)
sterzhen('par-vyhlop', (X0 + 0.05, YC + 0.12, ZO - 0.1), (X0 + 0.05, YC + 0.12, ZO + RP + 0.65), 0.035, M['med'], par)

# ── штоки, ползуны, качающиеся рычаги (каждая сторона — свой подузел, чтобы ходить в такт) ─────────────
shtoki = uzel('shtoki-i-rychagi', razbor=(0, 0, 0.55), metka=(-0.45, -0.5, 1.0))
SHT = []
for k, s in enumerate((-1, 1)):
    y = s * YC
    e = bpy.data.objects.new(f'shtok-{k + 1}', None); sc.collection.objects.link(e); e.parent = shtoki; SHT.append(e)
    sterzhen('shtok', (X1 - 0.05, y, ZO), (0.30, y, ZO), 0.028, M['blesk'], e, seg=24)
    box('polzun', (0.14, 0.2, 0.11), (-0.41, y, ZO), M['kraska'], e, fask=0.015)
    sterzhen('polzun-palec', (-0.41, y - 0.12, ZO), (-0.41, y + 0.12, ZO), 0.02, M['blesk'], e)
    # рычаг к золотнику соседней стороны (схема Вортингтона — допущение по внешнему виду)
    box('rychag', (0.04, 0.03, 0.42), (-0.41, y + s * 0.12, ZO + 0.30), M['kraska'], e, fask=0.008)
    sterzhen('zolotnikovaya-tyaga', (-0.41, y + s * 0.12, ZO + 0.50), (X1 - 0.05, y + s * 0.12, ZO + 0.50), 0.012, M['blesk'], e)
sterzhen('kachalnyj-val', (-0.41, -YC - 0.2, ZO + 0.5), (-0.41, YC + 0.2, ZO + 0.5), 0.022, M['blesk'], shtoki)
for s in (-1, 1):
    box('kachalnyj-kronshtein', (0.08, 0.05, 0.36), (-0.41, s * (YC + 0.2), ZO + 0.34), M['kraska'], shtoki, fask=0.01)

# ── нефтяная (насосная) часть: литой корпус с двумя цилиндрами ─────────────────────────────────────────
NX0, NX1 = 0.20, 0.90
neft_c = uzel('nasos-neftyanoy-cilindr', razbor=(0.25, -0.95, 0.0), metka=(0.55, -0.62, 0.62))
box('nf-korpus', (NX1 - NX0, 1.12, 0.52), ((NX0 + NX1) / 2, 0, 0.64), M['kraska'], neft_c, fask=0.05)
box('nf-podoshva', (NX1 - NX0 + 0.08, 1.2, 0.06), ((NX0 + NX1) / 2, 0, 0.41), M['kraska'], neft_c, fask=0.02)
RN = RAZMERY['NEFT_D'] / 2 + 0.05
for s in (-1, 1):
    y = s * YC
    flanec('nf-kryshka', (NX1, y, ZO), (1, 0, 0), 0.0, RN + 0.04, 0.04, M['kraska'], neft_c, n_bolt=10)
    lathe('nf-kryshka-kupol', [(0, 0.075), (0.06, 0.07), (RN - 0.01, 0.04)], M['kraska'], neft_c, seg=48, at=osi((NX1, y, ZO), (1, 0, 0)))
    flanec('nf-salnik', (NX0 - 0.06, y, ZO), (1, 0, 0), 0.03, 0.075, 0.06, M['latun'], neft_c, n_bolt=4)
for x in (0.36, 0.74):
    flanec('nf-luk', (x, -0.56, 0.64), (0, -1, 0), 0.0, 0.11, 0.025, M['kraska'], neft_c, n_bolt=8)
# всасывающий патрубок 4″ вниз, к резервуару промысла (допущение)
flanec('nf-vsas-fl', (0.55, -0.56, 0.47), (0, -1, 0), 0.05, 0.1, 0.022, M['kraska'], neft_c, n_bolt=6)
sterzhen('nf-vsas', (0.55, -0.58, 0.47), (0.55, -0.80, 0.47), 0.057, M['stal'], neft_c, seg=32)
for k in range(9):
    a0, a1 = math.pi / 2 * k / 9, math.pi / 2 * (k + 1) / 9
    p0 = Vector((0.55, -0.80 - 0.15 * math.sin(a0), 0.47 - 0.15 * (1 - math.cos(a0))))
    p1 = Vector((0.55, -0.80 - 0.15 * math.sin(a1), 0.47 - 0.15 * (1 - math.cos(a1))))
    sterzhen('nf-vsas', p0, p1 + (p1 - p0) * 0.04, 0.057, M['stal'], neft_c, seg=32)
sterzhen('nf-vsas', (0.55, -0.95, 0.32), (0.55, -0.95, 0.0), 0.057, M['stal'], neft_c, seg=32)

# ── клапанная коробка над насосными цилиндрами ────────────────────────────────────────────────────────
kl = uzel('klapannaya-korobka', razbor=(0.15, 0, 0.42), metka=(0.55, -0.45, 1.12))
box('kl-korpus', (0.66, 1.02, 0.18), ((NX0 + NX1) / 2, 0, 0.99), M['kraska'], kl, fask=0.03)
for s in (-1, 1):
    y = s * 0.27
    box('kl-kryshka', (0.5, 0.36, 0.03), ((NX0 + NX1) / 2, y, 1.095), M['kraska'], kl, fask=0.012)
    for x in np.linspace(NX0 + 0.12, NX1 - 0.12, 4):
        for yy in (y - 0.15, y + 0.15):
            bolty('kl-bolt', (x, yy, 1.11), (0, 0, 1), 0.0, 1, 0.013, M['temn'], kl)
# нагнетательный патрубок к нитке
flanec('kl-nagnet', (NX1, 0, ZT), (1, 0, 0), 0.0, 0.085, 0.03, M['kraska'], kl, n_bolt=0)
lathe('kl-nagnet-truba', [(0.0, 0), (0.06, 0), (0.06, 0.02), (RO + 0.008, 0.06), (RO + 0.008, X_PUSK - NX1 - 0.024)],
      M['kraska'], kl, seg=40, at=osi((NX1 + 0.03, 0, ZT), (1, 0, 0)))
flanec('kl-nagnet-fl', (X_PUSK - 0.024, 0, ZT), (1, 0, 0), RO, 0.085, 0.024, M['kraska'], kl, n_bolt=6)
sterzhen('kl-stoyak', (NX1 + 0.02, 0, 0.9), (NX1 + 0.02, 0, ZT + 0.05), 0.045, M['kraska'], kl, seg=32)

# ── воздушный колпак (сглаживает толчки поршней) ──────────────────────────────────────────────────────
kol = uzel('vozdushnyj-kolpak', razbor=(0.15, 0, 0.82), metka=(0.55, 0, 1.75))
pr = [(0, 1.08), (0.13, 1.08), None, (0.17, 1.08), (0.17, 1.11), None, (0.135, 1.11), (0.135, 1.5)]
for k in range(1, 9):
    f = math.pi / 2 * k / 8; pr.append((0.135 * math.cos(f), 1.5 + 0.12 * math.sin(f)))
lathe('kolpak', pr, M['kraska'], kol, seg=64, at=Matrix.Translation(((NX0 + NX1) / 2, 0, 0)))
bolty('kolpak-bolt', ((NX0 + NX1) / 2, 0, 1.11), (0, 0, 1), 0.155, 10, 0.012, M['temn'], kol)
lathe('kolpak-probka', [(0, 1.64), (0.025, 1.64), (0.025, 1.6)], M['latun'], kol, seg=6, at=Matrix.Translation(((NX0 + NX1) / 2, 0, 0)))

# ── манометр на нагнетании ────────────────────────────────────────────────────────────────────────────
man = uzel('manometr', razbor=(0.3, -0.45, 0.45), metka=(0.98, -0.1, 1.15))
MX, MZ = 0.98, 0.98
sterzhen('man-sifon', (MX, 0, ZT + RO), (MX, 0, MZ - 0.12), 0.009, M['med'], man)
tor('man-petlya', 0.04, 0.009, osi((MX, 0, MZ - 0.16), (0, 1, 0)), M['med'], man, seg=24, k=8)
lathe('man-kran', [(0, -0.03), (0.02, -0.03), (0.024, 0), (0.02, 0.03), (0, 0.03)], M['latun'], man, seg=6, at=osi((MX, 0, MZ - 0.24), (0, 0, 1)))
sterzhen('man-kran-ruchka', (MX, 0, MZ - 0.24), (MX - 0.06, -0.03, MZ - 0.24), 0.006, M['latun'], man, seg=8)
lathe('man-shtucer', [(0, 0), (0.012, 0), (0.012, 0.03), (0.018, 0.04), (0.018, 0.05)], M['latun'], man, seg=6, at=osi((MX, 0, MZ - 0.115), (0, 0, 1)))
atm = osi((MX, 0.0, MZ), (0, -1, 0))
lathe('man-korpus', [(0, 0.03), (0.075, 0.03), (0.082, 0.02), (0.082, -0.02), (0.075, -0.03), None, (0.075, -0.03), (0.068, -0.03)],
      M['latun'], man, seg=64, at=atm, tile=0.15)
lathe('man-obod', [(0.066, -0.03), (0.084, -0.03), (0.086, -0.036), (0.082, -0.042), (0.066, -0.040)], M['latun'], man, seg=64, at=atm, tile=0.15)
# циферблат — плоский диск с текстурой (UV — проекцией)
vs, fs, us = [(0, 0, 0)], [], [(0.5, 0.5)]
for i in range(64):
    a = TAU * i / 64; vs.append((0.066 * math.cos(a), 0.066 * math.sin(a), 0)); us.append((0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)))
for i in range(64): fs.append((0, 1 + i, 1 + (i + 1) % 64))
vs = [tuple(atm @ Matrix.Translation((0, 0, -0.031)) @ Vector(v)) for v in vs]
mesh_obj('man-ciferblat', vs, fs, us, M['cifer'], man, smooth=False)
strelka = box('man-strelka', (0.004, 0.055, 0.003), (0, 0.02, 0), M['temn'], man, fask=0.0)
strelka.matrix_parent_inverse = Matrix.Identity(4)
sm = atm @ Matrix.Translation((0, 0, -0.034)) @ Matrix.Rotation(math.radians(-25), 4, 'Z')
for v in strelka.data.vertices: v.co = sm @ v.co
lathe('man-os', [(0, -0.037), (0.007, -0.037), (0.007, -0.031)], M['latun'], man, seg=16, at=atm)
lathe('man-steklo', [(0, -0.0385), (0.068, -0.0385)], M['steklo'], man, seg=48, at=atm)

# ── нитка трубы ──────────────────────────────────────────────────────────────────────────────────────
AX = lambda x: osi((x, 0, ZT), (1, 0, 0))
truba = uzel('truba', metka=(8.0, 0, ZT + 0.1))
P = RAZMERY['SHAG_REZBY']; LR = RAZMERY['L_REZBY']; HR = 0.0018
def kusok(x0, x1, rodit, nachalo_rez=False, konec_rez=False, mat_=None):
    """Отрезок трубы: снаружи окалина, внутри — тёмная полость; концы под резьбу отдельно (узел rezba)."""
    a = x0 + (LR if nachalo_rez else 0); b = x1 - (LR if konec_rez else 0)
    lathe('truba', [(RO, 0), (RO, b - a)], mat_ or M['stal'], rodit, seg=40, at=AX(a), tile=0.6)
    lathe('truba-vnutr', [(RI, b - a), (RI, 0)], M['temn'], rodit, seg=24, at=AX(a), tile=0.6)
def rezba(x_start, napr, rodit):
    """Нарезка конической резьбы: пилообразный профиль, конусность 1:16 по диаметру."""
    pr = []
    n = int(LR / P)
    for k in range(n + 1):
        z = k * P; rr = RO - (LR - z) / 32 if napr > 0 else RO - z / 32
        pr += [(rr - HR, z), (rr, z + P * 0.5)]
    pr = [(RI, 0)] + pr[:-1] + [(RI, pr[-1][1])]
    if napr < 0:
        pr = [(r, LR - z) for r, z in pr][::-1]
    return lathe('rezba', pr, M['blesk'], rodit, seg=40, at=AX(x_start), tile=0.15)

flanec('truba-fl', (X_PUSK, 0, ZT), (1, 0, 0), RO, 0.085, 0.024, M['kraska'], truba, n_bolt=6)
kusok(X_PUSK + 0.02, X_MUFTA - 0.002, truba, konec_rez=True)
kusok(X_MUFTA + 0.002, X_RZ0, truba, nachalo_rez=True)
kusok(X_RZ1, X_MUFTA + 6.1 - 0.002, truba)
kusok(X_MUFTA + 6.1 + 0.002, X_KON, truba)
lathe('truba-torec', [(RI, 0), (RO, 0)], M['blesk'], truba, seg=40, at=AX(X_KON))
# вторая муфта (неподвижная) — та же форма, что и разборная
def mufta_geom(imya, x, rodit):
    L = RAZMERY['MUFTA_L']; R = RAZMERY['MUFTA_D'] / 2; f = 0.006
    return lathe(imya, [(RO + 0.001, -L / 2), (R - f, -L / 2), (R, -L / 2 + f), (R, L / 2 - f), (R - f, L / 2), (RO + 0.001, L / 2)],
                 M['mufta'], rodit, seg=48, at=AX(x), tile=0.3)
mufta_geom('truba-mufta', X_MUFTA + 6.1, truba)

rez = uzel('rezba', metka=(X_MUFTA - 0.04, 0, ZT + 0.08))
rezba(X_MUFTA - 0.002 - LR, +1, rez); rezba(X_MUFTA + 0.002, -1, rez)
muf = uzel('mufta', razbor=(0.26, 0, 0), metka=(X_MUFTA, 0, ZT + 0.30))
mufta_geom('mufta', X_MUFTA, muf)

# разрез: стенка без сектора, обращённого к зрителю (−Y и вверх); торцы и кромки — красные
rz = uzel('razrez-truby', metka=(X_RZ0 + 0.5, 0, ZT + 0.09))
A0, A1 = math.radians(-20), math.radians(190)    # оставленная дуга (в локальных осях AX: y = r·sin a, z = −r·cos a)
Lr = X_RZ1 - X_RZ0
lathe('razrez-stenka', [(RO, 0), (RO, Lr)], M['stal'], rz, seg=40, at=AX(X_RZ0), a0=A0, a1=A1, tile=0.6)
lathe('razrez-vnutr', [(RI, Lr), (RI, 0)], M['blesk'], rz, seg=40, at=AX(X_RZ0), a0=A0, a1=A1, tile=0.6)
for a in (A0, A1):         # кромки разреза — полосы от RI до RO вдоль всей длины
    at = AX(X_RZ0); ca, sa = math.cos(a), math.sin(a)
    vs = [tuple(at @ Vector((r * ca, r * sa, z))) for r, z in ((RI, 0), (RO, 0), (RO, Lr), (RI, Lr))]
    mesh_obj('razrez-kromka', vs, [(0, 1, 2, 3) if a == A1 else (3, 2, 1, 0)], [(0, 0), (0.05, 0), (0.05, 2), (0, 2)], M['srez'], rz, smooth=False)
for x in (X_RZ0, X_RZ1):   # торцы целой трубы на границах разреза
    lathe('razrez-torec', [(RI, 0), (RO, 0)] if x == X_RZ1 else [(RO, 0), (RI, 0)], M['srez'], rz, seg=40, at=AX(x), a0=A1, a1=A0 + TAU)
    lathe('razrez-torec', [(RI, 0), (RO, 0)] if x == X_RZ1 else [(RO, 0), (RI, 0)], M['stal'], rz, seg=40, at=AX(x), a0=A0, a1=A1)
neft = uzel('razrez-neft', metka=(X_RZ0 + 1.0, 0, ZT + 0.05))
lathe('neft', [(0, 0.0), (RI - 0.0008, 0.0), (RI - 0.0008, Lr), (0, Lr)], M['neft'], neft, seg=48, at=AX(X_RZ0), tile=0.12)

# опоры: деревянные козлы с седлом и хомутом (допущение)
op = uzel('opory', metka=(1.9, -0.3, 0.2))
def opora(x, rodit):
    box('opora-brus', (0.12, 0.62, 0.1), (x, 0, ZT - RO - 0.05), M['derevo'], rodit, fask=0.012)
    for s in (-1, 1):
        box('opora-noga', (0.1, 0.1, ZT - RO - 0.1), (x, s * 0.24, (ZT - RO - 0.1) / 2), M['derevo'], rodit, fask=0.012,
            rot=Matrix.Rotation(s * math.radians(-8), 4, 'X'))
    lathe('opora-homut', [(RO + 0.001, -0.02), (RO + 0.008, -0.02), (RO + 0.008, 0.02), (RO + 0.001, 0.02)], M['temn'], rodit, seg=32,
          at=AX(x), a0=math.radians(-90), a1=math.radians(90))
    for s in (-1, 1): bolty('opora-bolt', (x, s * (RO + 0.025), ZT - RO), (0, 0, 1), 0, 1, 0.012, M['temn'], rodit)
OPORY_X = [1.85, 5.8, 9.9, 13.4]
for x in OPORY_X: opora(x, op)

# земля (в glb — тоже: просмотрщик прячет край туманом)
zem = uzel('zemlya')
vs = [(-12, -14, 0), (40, -14, 0), (40, 14, 0), (-12, 14, 0)] if MODE == 'glb' else [(-60, -80, 0), (220, -80, 0), (220, 80, 0), (-60, 80, 0)]
mesh_obj('zemlya', vs, [(0, 1, 2, 3)], [(v[0] / 2.5, v[1] / 2.5) for v in vs], M['pesok'], zem, smooth=False)

# дальняя нитка — только для кадров/снимков (уходит к горизонту, к Чёрному городу)
DAL = None
if MODE != 'glb':
    DAL = bpy.data.objects.new('dal', None); sc.collection.objects.link(DAL)
    x = X_MUFTA + 12.2
    while x < 160:
        kusok(x - 6.1 + 0.002 if x - 6.1 > X_KON else X_KON, x - 0.002, DAL); mufta_geom('dal-mufta', x, DAL); x += 6.1
    for xx in np.arange(17.0, 160, 3.8): opora(xx, DAL)

# ── слияние мешей по (родитель, материал) ─────────────────────────────────────────────────────────────
gr = defaultdict(list)
for ob in list(sc.objects):
    if ob.type == 'MESH': gr[(ob.parent.name, ob.active_material.name)].append(ob)
for (r_imya, m_imya), obs in gr.items():
    bpy.ops.object.select_all(action='DESELECT')
    for ob in obs: ob.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    if len(obs) > 1: bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = f'{r_imya}~{m_imya}'
    ob.data.set_sharp_from_angle(angle=math.radians(38))

# узел ставим в «центр масс» подписи: позиция узла = 0, метка — смещение (просмотрщику хватает)
PARTS = [o for o in sc.objects if o.type == 'MESH' and (DAL is None or o.parent != DAL)]

# ── сцена, свет, камера ──────────────────────────────────────────────────────────────────────────────
def svet_i_scena(w, h, samples):
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
    sc.cycles.samples = samples; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.seed = 1878; sc.cycles.use_animated_seed = False
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
    sc.cycles.max_bounces = 6; sc.cycles.glossy_bounces = 3; sc.cycles.transparent_max_bounces = 4
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
    sc.view_settings.view_transform = 'AgX'
    try: sc.view_settings.look = 'AgX - Punchy'
    except Exception: pass
    # мир: HDRI студии светит и отражается, но в кадре фон — тёмный (Is Camera Ray)
    wd = bpy.data.worlds.new('W'); sc.world = wd; wd.use_nodes = True
    N, L = wd.node_tree.nodes, wd.node_tree.links
    bg = N['Background']; env = N.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(HDR)
    mp = N.new('ShaderNodeMapping'); tc = N.new('ShaderNodeTexCoord'); mp.inputs['Rotation'].default_value = (0, 0, math.radians(110))
    L.new(tc.outputs['Generated'], mp.inputs['Vector']); L.new(mp.outputs['Vector'], env.inputs['Vector'])
    L.new(env.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = 0.55
    tmn = N.new('ShaderNodeBackground'); tmn.inputs['Color'].default_value = (0.010, 0.008, 0.007, 1)
    lp = N.new('ShaderNodeLightPath'); mx = N.new('ShaderNodeMixShader')
    L.new(lp.outputs['Is Camera Ray'], mx.inputs['Fac']); L.new(bg.outputs['Background'], mx.inputs[1]); L.new(tmn.outputs['Background'], mx.inputs[2])
    L.new(mx.outputs['Shader'], N['World Output'].inputs['Surface'])
    def area(imya, loc, cel, sx, sy, e, col):
        ld = bpy.data.lights.new(imya, 'AREA'); ld.shape = 'RECTANGLE'; ld.size, ld.size_y, ld.energy, ld.color = sx, sy, e, col
        ob = bpy.data.objects.new(imya, ld); sc.collection.objects.link(ob); ob.location = loc
        ob.rotation_euler = (Vector(cel) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return ob
    area('klyuch', (-3.0, -4.5, 4.2), (0, 0, 0.6), 3.0, 2.0, 1400, (1.0, 0.93, 0.84))      # тёплый ключ — бакинское солнце
    area('kontr', (3.5, 5.0, 2.6), (0, 0, 0.7), 4.0, 1.0, 1500, (0.75, 0.85, 1.0))          # холодный контровой
    area('kontr-truba', (9.0, 4.0, 2.2), (6, 0, ZT), 8.0, 0.6, 1100, (0.8, 0.88, 1.0))      # блик вдоль нитки
    area('verh', (0.0, 0.0, 4.5), (0, 0, 0), 2.5, 2.5, 500, (1.0, 0.98, 0.95))
    area('razrez', (4.2, -1.6, 1.7), (4.2, 0, ZT), 1.6, 0.6, 420, (1.0, 0.9, 0.8))           # подсветка нефти в разрезе
    cd = bpy.data.cameras.new('kamera'); cd.clip_start = 0.02; cd.clip_end = 400
    cam = bpy.data.objects.new('kamera', cd); sc.collection.objects.link(cam); sc.camera = cam
    return cam

def navesti(cam, pos, tgt, lens=35):
    cam.location = pos; cam.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = lens

def sm(a, b, t):
    u = max(0.0, min(1.0, (t - a) / (b - a))); return u * u * (3 - 2 * u)

ZADERZHKA = {'nasos-parovoy-cilindr': 0.0, 'shtoki-i-rychagi': 0.25, 'nasos-neftyanoy-cilindr': 0.4, 'klapannaya-korobka': 0.15,
             'vozdushnyj-kolpak': 0.05, 'manometr': 0.3, 'rama': 0.5}
def razobrat(e_nasos, e_mufta, t=0.0, porshni=True):
    """Ставит части по степени разборки (0 — собрано, 1 — разобрано) и фазе поршней. Чистая функция аргументов."""
    for imya, ob in UZLY.items():
        d = Vector(ob['razbor_z'])
        if imya == 'mufta':
            ob.location = d * e_mufta
            ob.rotation_euler = (e_mufta * TAU * 1.5, 0, 0)        # муфту отворачивают
        elif imya in ZADERZHKA:
            z = ZADERZHKA[imya] * 0.35
            ob.location = d * max(0.0, min(1.0, (e_nasos - z) / (1 - z)))
    for k, e in enumerate(SHT):                                        # поршни дуплекса ходят со сдвигом в четверть хода
        e.location = ((0.055 * math.sin(TAU * 0.55 * t + k * math.pi / 2)) if porshni else 0.0, 0, 0)

SNIMKI = [  # имя, камера, цель, объектив, разборка насоса, разборка муфты
    ('geroj',    (-2.45, -3.0, 1.3), (1.1, 0.35, 0.6), 28, 0.0, 0.0),
    ('razborka', (-2.0, -4.4, 2.3), (0.15, -0.25, 0.9), 27, 1.0, 1.0),
    ('razrez',   (2.15, -0.85, 1.05), (3.35, 0.05, 0.5), 30, 0.0, 1.0),
]
DUR, FPS = 10.0, 24
OBLET = [  # с, камера, цель, объектив
    (0.0, (-3.4, -2.9, 1.9), (0.5, 0.2, 0.65), 30),
    (2.2, (-0.6, -3.1, 1.25), (1.7, 0.1, 0.6), 32),
    (3.6, (1.75, -1.05, 0.9), (3.0, 0.1, 0.52), 38),
    (5.0, (1.2, -3.2, 1.9), (0.2, -0.3, 0.8), 28),
    (6.8, (-2.6, -4.1, 2.6), (0.0, -0.3, 0.9), 26),
    (8.6, (-3.9, -1.2, 2.2), (0.0, 0.0, 0.8), 28),
    (10.0, (-3.4, -2.9, 1.9), (0.5, 0.2, 0.65), 30),
]
def cr(p0, p1, p2, p3, t):
    p0, p1, p2, p3 = map(Vector, (p0, p1, p2, p3)); t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
def oblet(ts):
    T = [k[0] for k in OBLET]; i = max(0, min(len(T) - 2, sum(1 for x in T if x <= ts) - 1))
    u = (ts - T[i]) / (T[i + 1] - T[i]); u = u * u * (3 - 2 * u) * 0.4 + u * 0.6
    g = lambda j: OBLET[max(0, min(len(OBLET) - 1, j))]
    return cr(g(i - 1)[1], g(i)[1], g(i + 1)[1], g(i + 2)[1], u), cr(g(i - 1)[2], g(i)[2], g(i + 1)[2], g(i + 2)[2], u), g(i)[3] + (g(i + 1)[3] - g(i)[3]) * u
def stsenarij(ts):
    """Степени разборки в момент ts: муфта отворачивается 2,4–3,6 с; насос раскрывается 4,2–6,0 с; всё собирается 7,4–9,4 с."""
    return sm(4.2, 6.0, ts) - sm(7.4, 9.4, ts), sm(2.3, 3.5, ts) - sm(7.0, 8.4, ts)

def main():
    if MODE == 'glb':
        out = A[1]
        razobrat(0, 0, porshni=False)
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_yup=True, export_apply=True, export_extras=True,
                                  export_image_format='AUTO', export_materials='EXPORT', export_tangents=False)
        tri = 0
        for p in PARTS: p.data.calc_loop_triangles(); tri += len(p.data.loop_triangles)
        print('GLB', out, os.path.getsize(out), 'байт, треугольников', tri, 'мешей', len(PARTS))
        return
    w, h, smp = (int(A[-3]), int(A[-2]), int(A[-1])) if len(A) >= (5 if MODE == 'snimki' else 7) else (1920, 1080, 64)
    cam = svet_i_scena(w, h, smp)
    if MODE == 'snimki':
        d = A[1]; os.makedirs(d, exist_ok=True); only = os.environ.get('ONLY')
        for imya, pos, tgt, lens, en, em in SNIMKI:
            if only and only not in imya: continue
            razobrat(en, em, t=0.3); navesti(cam, pos, tgt, lens)
            sc.render.filepath = os.path.join(d, f'{imya}.png'); bpy.ops.render.render(write_still=True)
    elif MODE == 'kadry':
        d, a, b = A[1], int(A[2]), int(A[3]); os.makedirs(d, exist_ok=True)
        for f in range(a, b + 1):
            ts = f / FPS; en, em = stsenarij(ts)
            razobrat(en, em, t=ts); pos, tgt, lens = oblet(ts); navesti(cam, pos, tgt, lens)
            sc.render.filepath = os.path.join(d, f'f{f:05d}.png'); bpy.ops.render.render(write_still=True)

main()
