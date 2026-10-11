"""Голова зомби по листу «Голова зомби — ракурсы»: большой круглый череп-купол, глубокие глазницы-«скруглённые квадраты» с костным
ободом и тяжёлой бровью, бледные светящиеся глаза со светлым центром, грушевидная носовая полость, рот с ровными прямоугольными
зубами сверху и снизу и опущенной челюстью, впалые щёки, острые скулы, настоящие уши с завитком, трещины на коже.

part_head() / part_jaw() возвращают bmesh в системе части: начало — основание черепа на шее (head) / сустав челюсти (jaw), перёд — −Y.
Размеры — метры, уже в итоговом масштабе (голова от макушки до подбородка ≈ 0.295 м). Нижняя челюсть построена в опущенном
положении (рот открыт), поэтому в позе её не вращают. Кожа — текстура (UV считаются в конце), раны, кости и тени — цвет вершин.

Пропорции сняты с каркаса на листе (доля высоты от макушки): глаза 58%, низ носа 78%, зубы 87–95%, подбородок 100%;
ширина черепа ≈ 0.70 высоты, глубина ≈ 0.80. Координаты ниже даны до HEAD_SCALE.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import zone_lib as Z
import zombie_geo as G
from zombie_geo import (BONE, BONE_DK, DARK, DARK_BLUE, EYE, EYE2, EYE_COL, GUM, MISC, MOUTH, SKIN, frames, lerp, skin_f)

V = Vector
HEAD_SCALE = 0.95
JAW_PIVOT = (0.0, 0.020 * HEAD_SCALE, 0.030 * HEAD_SCALE)       # сустав челюсти в системе головы

# сечения черепа: (z, полуширина, вынос вперёд, вынос назад); перёд −Y. Большой купол, сужение книзу к скулам и верхней челюсти.
SKULL = [(0.222, 0.020, 0.022, 0.024), (0.212, 0.056, 0.056, 0.070), (0.194, 0.080, 0.082, 0.104), (0.166, 0.094, 0.092, 0.122),
         (0.138, 0.099, 0.098, 0.128), (0.108, 0.098, 0.102, 0.124), (0.080, 0.094, 0.102, 0.110), (0.050, 0.088, 0.100, 0.098),
         (0.022, 0.080, 0.096, 0.086), (-0.004, 0.066, 0.090, 0.072), (-0.028, 0.050, 0.082, 0.058), (-0.044, 0.042, 0.074, 0.050)]
WX, WF, WB = 1.17, 1.06, 1.14                   # масштаб ширины, выноса вперёд и назад (череп шире и глубже, как на листе)
SKULL = [(z, rx * WX, rf * WF, rb * WB) for z, rx, rf, rb in SKULL]
SEG_SKULL = 40
DENSE_RINGS = 52                                 # плотный череп прореживается до ~TARGET_TRIS треугольников
TARGET_TRIS = 780
EYES = ((-0.047, 0.048), (0.047, 0.048))         # (x, z) глазниц
SOCKET_R = 0.0265                                # радиус отверстия глазницы (восьмиугольник)
NOSE = (0.008, 0.0170)                           # носовая полость: (z центра, R); острие вверх, вытянута по высоте ×1.5


def _skull_ring(z, rx, rf, rb, n=None):
    n = n or (2.0 + 0.4 * G.smooth(0.12, -0.02, z))             # купол — почти эллипс, к челюсти чуть квадратнее
    pts = []
    for k in range(SEG_SKULL):
        t = k * math.tau / SEG_SKULL
        c, s = math.cos(t), math.sin(t)
        c = math.copysign(abs(c) ** (2.0 / n), c)
        s = math.copysign(abs(s) ** (2.0 / n), s)
        pts.append(V((rx * c, -s * (rf if s > 0 else rb), z)))
    return pts


def skull_color(p):
    """Череп: хаки-кожа, лоб и макушка светлее, вокруг глазниц и во впалых щеках — тени, на висках — проплешины до кости."""
    x, y, z = p
    c = skin_f(p, 3)
    t = G.noise(x * 2.4, y * 2.0, z * 2.8, 11)
    if t > 0.60 and z > 0.10:
        c = G.mix(c, (1.0, 0.95, 0.80), (t - 0.60) * 2.5)
    if y < -0.03:
        for ex, ez in EYES:
            d = math.hypot(x - ex, z - ez)
            c = tuple(v * (1.0 - 0.10 * math.exp(-(d / 0.036) ** 2)) for v in c)           # лёгкие тени вокруг глаз
        sh = math.exp(-(math.hypot(abs(x) - 0.052, z + 0.008) / 0.028) ** 2)
        c = tuple(v * (1.0 - 0.12 * sh) for v in c)                                         # впалые щёки чуть темнее
    return c


def ring_dent(verts, c, r0, w, d, axis):
    """Кольцевой валик (d<0 вдоль axis — наружу): смещение по гауссу от расстояния до окружности радиуса r0 вокруг c."""
    c, ax = V(c), V(axis).normalized()
    for v in verts:
        k = math.exp(-(((v.co - c).length - r0) / w) ** 2)
        if k > 0.02:
            v.co += ax * (d * k)


def _eval_modifiers(bm, setup, extra=()):
    """bmesh → временный объект → модификаторы (setup(ob, extras)) → bmesh результата (атрибуты сохраняются)."""
    me = bpy.data.meshes.new("_zh_tmp")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("_zh_tmp", me)
    Z.collection().objects.link(ob)
    junk = [ob]
    for i, cb in enumerate(extra):
        cme = bpy.data.meshes.new(f"_zh_x{i}")
        cb.to_mesh(cme)
        cb.free()
        co = bpy.data.objects.new(f"_zh_x{i}", cme)
        Z.collection().objects.link(co)
        junk.append(co)
    setup(ob, junk[1:])
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    nm = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    out = bmesh.new()
    out.from_mesh(nm)
    bpy.data.meshes.remove(nm)
    for o in junk:
        d = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(d)
    bm.free()
    return out


def decimate(bm, ratio):
    """Decimate (collapse, симметрия по X): остаются острые края черт лица, плоское сливается в крупные грани."""
    def setup(ob, _):
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.decimate_type, mod.ratio = "COLLAPSE", ratio
        mod.use_collapse_triangulate = True
        mod.use_symmetry, mod.symmetry_axis = True, "X"
    return _eval_modifiers(bm, setup)


def boolean_cut(bm, cutters):
    """Вычитает из bm тела-вырезы (список bmesh) булевой операцией Blender."""
    def setup(ob, cobs):
        for i, co in enumerate(cobs):
            mod = ob.modifiers.new(f"cut{i}", "BOOLEAN")
            mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", co
    return _eval_modifiers(bm, setup, cutters)


def _socket_cutter(c, rot_z, r_front, r_back, depth):
    """Восьмиугольный конус-вырез вдоль оси Y (узким концом внутрь): c — центр, поворот вокруг Z — чтобы смотрел чуть наружу."""
    cb = bmesh.new()
    M = (Matrix.Translation(c) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "X") @ Matrix.Rotation(math.pi / 8, 4, "Z"))
    bmesh.ops.create_cone(cb, cap_ends=True, segments=8, radius1=r_back, radius2=r_front, depth=depth, matrix=M)
    return cb


def _nose_cutter(zc, R, depth):
    """Треугольная призма острием вверх (груша носового отверстия, вытянута по высоте ×1.5): вершины заданы явно. Вырез идёт вдоль Y."""
    cb = bmesh.new()
    top, base, hw = zc + R * 1.5, zc - R * 0.75, R * 0.866
    y0, y1 = -0.083 - depth / 2, -0.083 + depth / 2
    f0 = [cb.verts.new((0, y0, top)), cb.verts.new((-hw, y0, base)), cb.verts.new((hw, y0, base))]
    f1 = [cb.verts.new((0, y1, top)), cb.verts.new((-hw, y1, base)), cb.verts.new((hw, y1, base))]
    cb.faces.new(f0)
    cb.faces.new(f1[::-1])
    for i in range(3):
        j = (i + 1) % 3
        cb.faces.new((f0[i], f0[j], f1[j], f1[i]))
    bmesh.ops.recalc_face_normals(cb, faces=list(cb.faces))
    return cb


def dense_rings():
    """Кольца черепа: линейная интерполяция таблицы SKULL по z на DENSE_RINGS уровней и сглаживание — плавные формы под вмятины."""
    zs = [r[0] for r in SKULL]
    out = []
    for i in range(DENSE_RINGS):
        z = zs[0] + (zs[-1] - zs[0]) * i / (DENSE_RINGS - 1)
        for a, b in zip(SKULL, SKULL[1:]):
            if a[0] >= z >= b[0]:
                k = (a[0] - z) / (a[0] - b[0]) if a[0] != b[0] else 0.0
                out.append([z] + [lerp(a[j], b[j], k) for j in (1, 2, 3)])
                break
    for _ in range(4):                                                        # сглаживание [1 2 1]
        new = [out[0]]
        for i in range(1, len(out) - 1):
            new.append([out[i][0]] + [(out[i - 1][j] + 2 * out[i][j] + out[i + 1][j]) / 4 for j in (1, 2, 3)])
        new.append(out[-1])
        out = new
    return out


def part_head(rnd):
    bm = bmesh.new()
    rings = [_skull_ring(*r) for r in dense_rings()]
    faces, rv = G.bridge(bm, rings, SKIN, skull_color, rnd, caps=(True, True), jit=0.0)
    verts = list({v for r in rv for v in r})

    # ---- рельеф лица (вмятины и выпуклости, симметрично)
    for sx in (-1, 1):
        G.dent(verts, (sx * 0.047, -0.102, 0.048), 0.036, 0.018, (0, 1, 0))                      # западение вокруг глазницы
        ring_dent(verts, (sx * 0.047, -0.106, 0.048), 0.034, 0.012, -0.014, (0, 1, 0))           # костный обод глазницы
        G.dent(verts, (sx * 0.047, -0.108, 0.077), 0.032, -0.028, (0, 1, 0))                     # тяжёлая бровь
        G.dent(verts, (sx * 0.084, -0.083, 0.014), 0.026, -0.026, (sx * 0.6, 1, 0))              # скула
        G.dent(verts, (sx * 0.103, -0.047, 0.030), 0.022, -0.012, (sx, 0.4, 0))                  # скуловая дуга к уху
        G.dent(verts, (sx * 0.070, -0.075, -0.010), 0.026, 0.034, (-sx * 0.7, 0.8, 0))           # впалая щека
        G.dent(verts, (sx * 0.108, -0.044, 0.080), 0.032, 0.020, (-sx, 0, 0))                    # висок
    G.dent(verts, (0, -0.110, 0.075), 0.022, -0.010, (0, 1, 0))                                  # межбровье
    G.dent(verts, (0, -0.108, 0.034), 0.018, 0.012, (0, 1, 0))                                   # переносица
    G.dent(verts, (0, -0.110, 0.192), 0.044, 0.012, (0, 1, 0))                                   # лоб скошен

    # ---- крупные грани: прореживание плотного черепа, затем глазницы и носовая полость (булева операция)
    bm = decimate(bm, min(1.0, TARGET_TRIS / max(1, sum(len(f.verts) - 2 for f in bm.faces))))
    cuts = [_socket_cutter((sx * 0.047, -0.091, 0.048), sx * 0.10, SOCKET_R, SOCKET_R * 0.80, 0.075) for sx in (-1, 1)]
    cuts.append(_nose_cutter(*NOSE[:1], NOSE[1], 0.050))
    bm = boolean_cut(bm, cuts)
    G.paint(bm, list(bm.faces), skull_color, rnd, SKIN, 0.15)

    def in_socket(p):
        return p.y < -0.040 and any(math.hypot(p.x - ex, p.z - ez) <= SOCKET_R + 0.0005 for ex, ez in EYES)

    def in_nose(p, tol):
        zc, R = NOSE
        top, base = zc + R * 1.5, zc - R * 0.75
        return -0.118 < p.y < -0.046 and base - tol <= p.z <= top + tol and abs(p.x) <= 0.3849 * (top - p.z) + tol

    for f in bm.faces:                                                      # стенки и дно вырезов — тёмная сине-серая полость
        c = f.calc_center_median()
        if all(in_socket(v.co) for v in f.verts) or (in_nose(c, 0.0015) and all(in_nose(v.co, 0.0045) for v in f.verts)):
            G.paint(bm, [f], DARK_BLUE, rnd, SKIN, 0.0)

    # ---- костные гребни, спроецированные на поверхность черепа: обод глазниц, надбровная дуга, скуловые дуги
    tree = BVHTree.FromBMesh(bm)
    BONE_SKIN = lambda p: tuple(c * 1.03 for c in skin_f(p, 9))

    def surf(x, z, off=0.0):
        hit = tree.ray_cast(V((x, -0.32, z)), V((0, 1, 0)))
        return None if hit[0] is None else hit[0] + V((0, -off, 0))

    def ridge(pts, r, closed=False, seg=5):
        P = [surf(x, z, r * 0.10) for x, z in pts]
        P = [q for q in P if q is not None]
        if closed and len(P) > 2:
            P.append(P[0].copy())
        if len(P) < 2:
            return
        fr = frames(P, (0, -1, 0))
        rings = [G.ring(q, N, B, r, r, seg, rnd=rnd, jit=0.08) for (T, N, B), q in zip(fr, P)]
        faces_, rv_ = G.bridge(bm, rings, SKIN, BONE_SKIN, rnd, caps=(not closed, not closed), closed=True)
        if closed:
            bmesh.ops.remove_doubles(bm, verts=list({v for r_ in rv_ for v in r_}), dist=1e-5)

    for ex, ez in EYES:
        ridge([(ex + (SOCKET_R + 0.0030) * math.cos(t), ez + (SOCKET_R + 0.0030) * math.sin(t)) for t in [k * math.tau / 14 for k in range(14)]],
              0.0046, closed=True)

    # ---- трещины на коже: тонкие тёмные канавки, спроецированные на поверхность
    def crack(pts, r=0.0017):
        P = [surf(x, z, -0.0006) for x, z in pts]
        P = [q for q in P if q is not None]
        if len(P) > 1:
            G.tube(bm, rnd, P, [r] * len(P), 3, SKIN, (0.035, 0.030, 0.025), caps=(True, True))

    crack([(0.016, 0.200), (0.026, 0.180), (0.014, 0.162), (0.018, 0.146)])
    crack([(0.026, 0.180), (0.046, 0.172), (0.060, 0.158)])
    crack([(-0.076, 0.034), (-0.068, 0.014), (-0.074, -0.006), (-0.064, -0.020)])
    crack([(0.070, 0.106), (0.080, 0.088), (0.074, 0.070)])

    # ---- глаза: крупные бледно-серые мягко светящиеся шары, глубоко в глазницах + светлая сердцевина
    for sx in (-1, 1):
        G.blob(bm, rnd, (sx * 0.047, -0.049, 0.047), (0.0190, 0.0155, 0.0190), EYE_COL, EYE, sub=2, jitter=0.0)
        G.blob(bm, rnd, (sx * 0.047, -0.0635, 0.047), (0.0088, 0.0040, 0.0088), (1, 1, 1), EYE2, sub=2, jitter=0.0)

    # ---- нос: тонкая костяная спинка над полостью
    G.tube(bm, rnd, [V((0, -0.103, 0.068)), V((0, -0.107, 0.056)), V((0, -0.105, 0.044))], [(0.003, 0.0045), (0.0052, 0.0068), (0.0045, 0.0074)],
           4, SKIN, lambda p: skin_f(p, 7), up=(0, -1, 0), caps=(True, True))

    # ---- уши
    for sx in (-1, 1):
        ear(bm, rnd, sx)

    # ---- верхняя челюсть: массивный костный блок под носом, десна, ровные зубы, тёмная полость рта
    arc_pts = [(0.036 * math.sin(t), -0.038 - 0.046 * math.cos(t)) for t in [(-1.10 + 2.20 * i / 14) for i in range(15)]]
    bone_c = lambda p: tuple(c * 1.06 for c in skin_f(p, 9))
    G.tube(bm, rnd, [V((x, y, -0.011)) for x, y in arc_pts], [(0.0125, 0.0120)] * 15, 6, SKIN, bone_c, up=(0, 0, 1), caps=(True, True), jit=0.03)   # блок
    G.tube(bm, rnd, [V((x * 0.98, y + 0.004, 0.004)) for x, y in arc_pts], [(0.0110, 0.0150)] * 15, 6, SKIN, bone_c, up=(0, 0, 1), caps=(True, True), jit=0.03)  # мост к носу
    G.tube(bm, rnd, [V((x, y - 0.002, -0.0235)) for x, y in arc_pts], [(0.0038, 0.0052)] * 15, 5, MISC, GUM, caps=(True, True))
    teeth_arc(bm, rnd, (0, -0.038, -0.0215), 0.036, 0.046, 9, -1.10, 1.10, 0.0165, True)
    G.blob(bm, rnd, (0, -0.030, -0.048), (0.038, 0.034, 0.024), DARK, MISC, sub=1, jitter=0.04)

    # ---- шея внутри черепа (стык с шеей туловища)
    G.tube(bm, rnd, [V((0, 0.012, -0.020)), V((0, 0.014, -0.080))], [(0.040, 0.042)] * 2, 8, SKIN, lambda p: skin_f(p, 2), up=(0, -1, 0),
           caps=(False, True))
    G.facet(bm, rnd)
    bmesh.ops.scale(bm, vec=(HEAD_SCALE,) * 3, verts=bm.verts)
    G.uv_pass(bm)
    return bm


def ear(bm, rnd, sx):
    """Крупное ухо: толстая пластина, высокий завиток по краю, тёмная чаша, козелок, мочка — плотно прижато к черепу позади скулы."""
    cx, cy, cz = sx * 0.097, 0.022, 0.036
    a = sx * 0.30
    ca, sa = math.cos(a), math.sin(a)

    def P(x, y, z):                                                         # x — наружу, y — назад, z — вверх (локально)
        xx = sx * x
        return V((cx + xx * ca - y * sa, cy + xx * sa + y * ca, cz + z))

    G.blob(bm, rnd, P(0.004, 0.002, 0.0), (0.0140, 0.024, 0.036), lambda p: tuple(c * 0.92 for c in skin_f(p, 5)), SKIN, jitter=0.07, rot=(0, 0, a))   # пластина
    loop = [P(0.014, 0.003 + 0.023 * math.cos(t), 0.035 * math.sin(t)) for t in [k * math.tau / 10 for k in range(10)]]
    loop.append(loop[0].copy())
    rings = []
    for (T, N, B), p in zip(frames(loop, (sx * ca, sx * sa, 0)), loop):
        rings.append(G.ring(p, N, B, 0.0075, 0.0075, 5, rnd=rnd, jit=0.06))
    faces, rv = G.bridge(bm, rings, SKIN, lambda p: skin_f(p, 5), rnd, caps=(False, False), closed=True)
    bmesh.ops.remove_doubles(bm, verts=list({v for r in rv for v in r}), dist=1e-5)                                       # завиток
    G.blob(bm, rnd, P(0.012, 0.006, 0.002), (0.0050, 0.0140, 0.0240), lambda p: tuple(c * 0.40 for c in skin_f(p, 5)), SKIN, jitter=0.08, rot=(0, 0, a))   # чаша
    G.blob(bm, rnd, P(0.013, -0.012, -0.006), (0.0070, 0.0075, 0.0100), lambda p: skin_f(p, 5), SKIN, jitter=0.10, rot=(0, 0, a))                   # козелок
    G.blob(bm, rnd, P(0.011, 0.004, -0.036), (0.0085, 0.0095, 0.0110), lambda p: skin_f(p, 5), SKIN, jitter=0.10, rot=(0, 0, a))                    # мочка


def teeth_arc(bm, rnd, c, rx, ry, n, a0, a1, h, upper):
    """Ряд ровных прямоугольных зубов по дуге эллипса (перёд — −Y): резцы шире, клыки чуть острее, цвет слоновой кости с желтизной."""
    for i in range(n):
        t = a0 + (a1 - a0) * (i + 0.5) / n
        x = c[0] + rx * math.sin(t)
        y = c[1] - ry * math.cos(t)
        mid = abs(t) < 0.45
        canine = abs(abs(t) - 0.62 * (a1 - a0) / 2.0) < 0.2 and not mid and i in (1, n - 2)
        hh = h * (1.12 if canine else 1.0) * rnd.uniform(0.88, 1.05)
        w = 0.0098 if mid else 0.0086
        col = G.mix(BONE, BONE_DK, rnd.uniform(0.0, 0.40))
        sgn = -1 if upper else 1
        G.box(bm, rnd, (x, y, c[2] + sgn * (hh / 2 - 0.001)), (w, 0.0062, hh), col,
              rot=(math.pi if upper else 0.0, rnd.uniform(-0.05, 0.05), -t), taper=(0.80 if not canine else 0.45, 0.85))


def part_jaw(rnd):
    """Нижняя челюсть в опущенном положении: U-образная «лента» — подбородок и щёки до скул (рот-овал), ровные зубы, тёмный язык.
    Шарнир — у ушей; геометрия строится в системе головы (до HEAD_SCALE) и сдвигается на −JAW_PIVOT."""
    bm = bmesh.new()
    # (|x|, y, z центра, a вертикальная, b толщина): ветви челюсти поднимаются под скулы, спереди — короткий острый подбородок
    P = [(0.056, 0.026, 0.018, 0.030, 0.008), (0.056, 0.020, -0.012, 0.046, 0.009), (0.049, 0.004, -0.040, 0.044, 0.010),
         (0.038, -0.026, -0.060, 0.032, 0.010), (0.022, -0.056, -0.074, 0.016, 0.010), (0.008, -0.070, -0.078, 0.011, 0.011)]
    left = [V((-x, y, z)) for x, y, z, a, b in P]
    right = [V((x, y, z)) for x, y, z, a, b in reversed(P)]
    rad = [(a, b) for x, y, z, a, b in P]
    G.tube(bm, rnd, left + right, rad + list(reversed(rad)), 6, SKIN, lambda p: skin_f(p, 4), up=(0, 0, 1), caps=(True, True), jit=0.06)
    teeth_arc(bm, rnd, (0, -0.036, -0.074), 0.033, 0.043, 9, -1.10, 1.10, 0.0145, False)
    G.blob(bm, rnd, (0, -0.042, -0.068), (0.018, 0.024, 0.006), MOUTH, MISC, sub=1, jitter=0.05)                      # язык
    for v in bm.verts:
        v.co -= V((0.0, 0.020, 0.030))
    G.facet(bm, rnd)
    bmesh.ops.scale(bm, vec=(HEAD_SCALE,) * 3, verts=bm.verts)
    G.uv_pass(bm)
    return bm
