"""Голова зомби по арт-листу («Крупный план (голова)»): круглый гладкий череп, глубокие круглые глазницы с костным ободом и тяжёлой
бровью, бледно-серые светящиеся глаза, маленький костяной нос с ноздрями, рот-овал «крика» с мелкими неровными зубами, впалые щёки,
острый подбородок, настоящие уши с завитком, тонкая шея.

part_head() / part_jaw() возвращают bmesh в системе части: начало — основание черепа на шее (head) / сустав челюсти (jaw), перёд — −Y.
Размеры — метры, уже в итоговом масштабе (голова от макушки до подбородка ≈ 0.30 м). Нижняя челюсть построена уже в опущенном
положении (рот открыт), поэтому в позе её не вращают. Кожа — текстура (UV считаются в конце), раны, кости и тени — цвет вершин.

Раскладка по высоте (z от основания черепа): макушка 0.215, надбровье 0.100, глаза 0.072, скулы 0.040, кончик носа 0.025,
линия верхних зубов 0.000, подбородок −0.096 (рот открыт).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import zone_lib as Z
import zombie_geo as G
from zombie_geo import BONE, BONE_DK, DARK, EYE, EYE_COL, GUM, MISC, MOUTH, SKIN, frames, lerp, skin_f

V = Vector
JAW_PIVOT = (0.0, 0.020, 0.030)                  # сустав челюсти в системе головы

# сечения черепа: (z, полуширина, вынос вперёд, вынос назад); перёд −Y. Сужается книзу, как настоящий череп.
SKULL = [(0.205, 0.018, 0.020, 0.022), (0.196, 0.048, 0.050, 0.060), (0.180, 0.070, 0.072, 0.092), (0.153, 0.084, 0.082, 0.106),
         (0.127, 0.088, 0.088, 0.112), (0.097, 0.088, 0.092, 0.108), (0.070, 0.082, 0.092, 0.094), (0.044, 0.073, 0.088, 0.082),
         (0.020, 0.057, 0.084, 0.064), (0.000, 0.043, 0.070, 0.050)]
SEG_SKULL = 40
DENSE_RINGS = 46                                 # плотный череп прореживается до ~TARGET_TRIS треугольников
TARGET_TRIS = 620
EYES = ((-0.038, 0.064), (0.038, 0.064))         # (x, z) глазниц
SOCKET_R = 0.0255                                # радиус отверстия глазницы


def _skull_ring(z, rx, rf, rb, n=2.2):
    pts = []
    for k in range(SEG_SKULL):
        t = k * math.tau / SEG_SKULL
        c, s = math.cos(t), math.sin(t)
        c = math.copysign(abs(c) ** (2.0 / n), c)
        s = math.copysign(abs(s) ** (2.0 / n), s)
        pts.append(V((rx * c, -s * (rf if s > 0 else rb), z)))
    return pts


def skull_color(p):
    """Череп: хаки-кожа, лоб и макушка чуть светлее, вокруг глазниц и во впалых щеках — тени, на висках — проплешины до кости."""
    x, y, z = p
    c = skin_f(p, 3)
    t = G.noise(x * 2.4, y * 2.0, z * 2.8, 11)
    if t > 0.60 and z > 0.10:
        c = G.mix(c, (1.0, 0.95, 0.80), (t - 0.60) * 2.5)
    if y < -0.03:
        for ex, ez in EYES:
            d = math.hypot(x - ex, z - ez)
            c = tuple(v * (1.0 - 0.22 * math.exp(-(d / 0.034) ** 2)) for v in c)           # лёгкие тени вокруг глаз
        sh = math.exp(-(math.hypot(abs(x) - 0.048, z - 0.012) / 0.026) ** 2)
        c = tuple(v * (1.0 - 0.38 * sh) for v in c)                                         # впалые щёки темнее
    return c


def ring_dent(verts, c, r0, w, d, axis):
    """Кольцевой валик (d<0 вдоль axis — наружу): смещение по гауссу от расстояния до окружности радиуса r0 вокруг c."""
    c, ax = V(c), V(axis).normalized()
    for v in verts:
        k = math.exp(-(((v.co - c).length - r0) / w) ** 2)
        if k > 0.02:
            v.co += ax * (d * k)


def boolean_cut(bm, cutters):
    """Вычитает из bm тела-вырезы (список bmesh) булевой операцией Blender; возвращает новый bmesh (атрибуты сохраняются)."""
    me = bpy.data.meshes.new("_zh_skull")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("_zh_skull", me)
    Z.collection().objects.link(ob)
    junk = [ob]
    for i, cb in enumerate(cutters):
        cme = bpy.data.meshes.new(f"_zh_cut{i}")
        cb.to_mesh(cme)
        cb.free()
        co = bpy.data.objects.new(f"_zh_cut{i}", cme)
        Z.collection().objects.link(co)
        junk.append(co)
        mod = ob.modifiers.new(f"cut{i}", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", co
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
    """Прореживает bmesh модификатором Decimate (collapse, симметрия по X): остаются острые края черт лица, плоское сливается в крупные грани."""
    me = bpy.data.meshes.new("_zh_dec")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("_zh_dec", me)
    Z.collection().objects.link(ob)
    mod = ob.modifiers.new("dec", "DECIMATE")
    mod.decimate_type, mod.ratio = "COLLAPSE", ratio
    mod.use_collapse_triangulate = True
    mod.use_symmetry, mod.symmetry_axis = True, "X"
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    nm = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    out = bmesh.new()
    out.from_mesh(nm)
    bpy.data.meshes.remove(nm)
    bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.meshes.remove(me)
    bm.free()
    return out


def _cone_cutter(c, rot_z, r_front, r_back, depth):
    """Конус-вырез вдоль оси Y (узким концом внутрь головы): c — центр, поворот вокруг Z — чтобы смотрел чуть наружу."""
    cb = bmesh.new()
    M = Matrix.Translation(c) @ Matrix.Rotation(rot_z, 4, "Z") @ Matrix.Rotation(math.pi / 2, 4, "X")
    bmesh.ops.create_cone(cb, cap_ends=True, segments=14, radius1=r_back, radius2=r_front, depth=depth, matrix=M)
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


def _tri_cutter(c, R, depth):
    """Треугольная призма (острием вверх) вдоль оси Y — вырез носовой полости; c — центр, R — радиус описанной окружности."""
    cb = bmesh.new()
    M = Matrix.Translation(c) @ Matrix.Rotation(math.pi / 2, 4, "X") @ Matrix.Rotation(math.pi / 2, 4, "Z")
    bmesh.ops.create_cone(cb, cap_ends=True, segments=3, radius1=R, radius2=R, depth=depth, matrix=M)
    return cb


def part_head(rnd):
    bm = bmesh.new()
    rings = [_skull_ring(*r) for r in dense_rings()]
    faces, rv = G.bridge(bm, rings, SKIN, skull_color, rnd, caps=(True, True), jit=0.0)
    verts = list({v for r in rv for v in r})

    # ---- рельеф лица (вмятины и выпуклости, симметрично)
    for sx in (-1, 1):
        G.dent(verts, (sx * 0.038, -0.091, 0.064), 0.031, 0.016, (0, 1, 0))                      # западение вокруг глазницы
        ring_dent(verts, (sx * 0.038, -0.095, 0.064), 0.031, 0.010, -0.011, (0, 1, 0))           # костный обод глазницы
        G.dent(verts, (sx * 0.037, -0.096, 0.094), 0.028, -0.024, (0, 1, 0))                     # тяжёлая бровь
        G.dent(verts, (sx * 0.068, -0.074, 0.036), 0.023, -0.021, (sx * 0.6, 1, 0))              # скула
        G.dent(verts, (sx * 0.082, -0.040, 0.048), 0.020, -0.010, (sx, 0.4, 0))                  # скуловая дуга к уху
        G.dent(verts, (sx * 0.050, -0.066, 0.008), 0.023, 0.032, (-sx * 0.7, 0.8, 0))            # впалая щека
        G.dent(verts, (sx * 0.087, -0.035, 0.092), 0.028, 0.016, (-sx, 0, 0))                    # висок
    G.dent(verts, (0, -0.098, 0.092), 0.020, -0.008, (0, 1, 0))                                  # межбровье
    G.dent(verts, (0, -0.096, 0.050), 0.016, 0.010, (0, 1, 0))                                   # переносица
    G.dent(verts, (0, -0.100, 0.172), 0.040, 0.010, (0, 1, 0))                                   # лоб скошен

    # ---- крупные грани: прореживание плотного черепа, затем круглые глазницы (булева операция)
    bm = decimate(bm, min(1.0, TARGET_TRIS / max(1, sum(len(f.verts) - 2 for f in bm.faces))))
    cuts = [_cone_cutter((sx * 0.038, -0.082, 0.064), sx * 0.10, SOCKET_R, SOCKET_R * 0.78, 0.075) for sx in (-1, 1)]
    cuts.append(_tri_cutter((0, -0.078, 0.030), 0.0175, 0.050))
    bm = boolean_cut(bm, cuts)
    G.paint(bm, list(bm.faces), skull_color, rnd, SKIN, 0.15)

    def in_hole(p):
        if p.y > -0.040:
            return False
        if any(math.hypot(p.x - ex, p.z - ez) <= SOCKET_R + 0.0005 for ex, ez in EYES):
            return True
        return 0.0200 <= p.z <= 0.0480 and abs(p.x) <= 0.0152 * (0.0480 - p.z) / 0.0280 + 0.0008      # носовая полость (острие вверх)

    for f in bm.faces:                                                      # стенки и дно вырезов — чёрные (грань целиком внутри)
        if all(in_hole(v.co) for v in f.verts):
            G.paint(bm, [f], DARK, rnd, SKIN, 0.0)

    # ---- глаза: бледно-серые светящиеся шары, утоплены в глазницах; тяжёлые веки-брови слегка прикрывают верх
    for sx in (-1, 1):
        G.blob(bm, rnd, (sx * 0.038, -0.060, 0.063), (0.0150, 0.0125, 0.0150), EYE_COL, EYE, sub=2, jitter=0.0)
        G.box(bm, rnd, (sx * 0.039, -0.080, 0.087), (0.040, 0.010, 0.0075), lambda p: tuple(c * 0.95 for c in skin_f(p, 8)),
              rot=(0.0, -sx * 0.30, 0.0), mi=SKIN)

    # ---- нос: полость вырезана; над ней — тонкая костяная спинка
    G.tube(bm, rnd, [V((0, -0.090, 0.066)), V((0, -0.095, 0.058)), V((0, -0.094, 0.052))], [(0.003, 0.0045), (0.0050, 0.0065), (0.0045, 0.0070)],
           4, SKIN, lambda p: skin_f(p, 7), up=(0, -1, 0), caps=(True, True))

    # ---- уши: C-образный завиток, внутренняя чаша, мочка
    for sx in (-1, 1):
        ear(bm, rnd, sx)

    # ---- верхние зубы, десна, тёмная полость рта
    arc = [V((0.027 * math.sin(t), -0.030 - 0.038 * math.cos(t), 0.003)) for t in [(-1.15 + 2.3 * i / 12) for i in range(13)]]
    G.tube(bm, rnd, arc, [(0.0040, 0.0050)] * len(arc), 5, MISC, GUM, caps=(True, True))
    teeth_arc(bm, rnd, (0, -0.030, 0.003), 0.027, 0.038, 8, -1.15, 1.15, 0.020, True)
    G.blob(bm, rnd, (0, -0.018, -0.030), (0.028, 0.026, 0.022), DARK, MISC, sub=1, jitter=0.04)

    # ---- шея внутри черепа (стык с шеей туловища)
    G.tube(bm, rnd, [V((0, 0.012, 0.015)), V((0, 0.014, -0.050))], [(0.034, 0.036)] * 2, 8, SKIN, lambda p: skin_f(p, 2), up=(0, -1, 0),
           caps=(False, True))
    G.facet(bm, rnd)
    G.uv_pass(bm)
    return bm


def ear(bm, rnd, sx):
    """Ухо на уровне глаз–носа, прижато к черепу позади скулы, смотрит наружу и чуть вперёд."""
    cx, cy, cz = sx * 0.076, 0.018, 0.044
    a = sx * 0.42
    ca, sa = math.cos(a), math.sin(a)

    def P(x, y, z):                                                         # x — наружу, y — назад, z — вверх (локально)
        xx = sx * x
        return V((cx + xx * ca - y * sa, cy + xx * sa + y * ca, cz + z))

    G.blob(bm, rnd, P(0.007, 0.004, 0.0), (0.0065, 0.019, 0.031), lambda p: tuple(c * 0.9 for c in skin_f(p, 5)), SKIN, jitter=0.07, rot=(0, 0, a))   # пластина
    loop = [P(0.013, 0.004 + 0.018 * math.cos(t), 0.030 * math.sin(t)) for t in [k * math.tau / 10 for k in range(10)]]
    loop.append(loop[0].copy())
    rings = []
    for (T, N, B), p in zip(frames(loop, (sx * ca, sx * sa, 0)), loop):
        rings.append(G.ring(p, N, B, 0.0050, 0.0050, 5, rnd=rnd, jit=0.05))
    faces, rv = G.bridge(bm, rings, SKIN, lambda p: skin_f(p, 5), rnd, caps=(False, False), closed=True)
    bmesh.ops.remove_doubles(bm, verts=list({v for r in rv for v in r}), dist=1e-5)                                       # завиток
    G.blob(bm, rnd, P(0.0105, 0.005, 0.002), (0.0040, 0.0100, 0.0175), lambda p: tuple(c * 0.55 for c in skin_f(p, 5)), SKIN, jitter=0.08, rot=(0, 0, a))   # чаша
    G.blob(bm, rnd, P(0.010, 0.004, -0.030), (0.0070, 0.0080, 0.0090), lambda p: skin_f(p, 5), SKIN, jitter=0.10, rot=(0, 0, a))                    # мочка


def teeth_arc(bm, rnd, c, rx, ry, n, a0, a1, h, upper):
    """Ряд мелких неровных зубов по дуге эллипса (перёд — −Y): разной длины, клыки острее, часть обломана; цвет старой кости."""
    for i in range(n):
        t = a0 + (a1 - a0) * (i + 0.5) / n
        x = c[0] + rx * math.sin(t)
        y = c[1] - ry * math.cos(t)
        k = 1.25 if i in (1, n - 2) else 1.0                                              # клыки длиннее
        if rnd.random() < 0.12:
            k = 0.45                                                                       # обломанный зуб
        hh = h * k * rnd.uniform(0.75, 1.10)
        w = 0.0085 if abs(t) < 0.55 else 0.0075
        col = G.mix(BONE, BONE_DK, rnd.uniform(0.0, 0.55))
        sgn = -1 if upper else 1
        G.box(bm, rnd, (x, y, c[2] + sgn * (hh / 2 - 0.001)), (w, 0.0055, hh), col,
              rot=(math.pi if upper else 0.0, rnd.uniform(-0.15, 0.15), -t), taper=(0.22, 0.45))


def part_jaw(rnd):
    """Нижняя челюсть в опущенном положении: U-образная «лента» — подбородок и щёки до скул (рот-овал), мелкие зубы, тёмный язык.
    Шарнир — у ушей; геометрия строится в системе головы и сдвигается на −JAW_PIVOT."""
    bm = bmesh.new()
    # (|x|, y, z центра, a вертикальная, b толщина): ветви челюсти поднимаются под скулы, спереди — низкий подбородок
    P = [(0.040, 0.022, 0.014, 0.030, 0.007), (0.038, 0.016, -0.010, 0.044, 0.008), (0.035, 0.002, -0.034, 0.046, 0.009),
         (0.028, -0.026, -0.050, 0.036, 0.009), (0.017, -0.050, -0.062, 0.020, 0.009), (0.007, -0.063, -0.066, 0.014, 0.010)]
    left = [V((-x, y, z)) for x, y, z, a, b in P]
    right = [V((x, y, z)) for x, y, z, a, b in reversed(P)]
    rad = [(a, b) for x, y, z, a, b in P]
    G.tube(bm, rnd, left + right, rad + list(reversed(rad)), 6, SKIN, lambda p: skin_f(p, 4), up=(0, 0, 1), caps=(True, True), jit=0.06)
    teeth_arc(bm, rnd, (0, -0.030, -0.052), 0.024, 0.035, 7, -1.05, 1.05, 0.016, False)
    G.blob(bm, rnd, (0, -0.036, -0.050), (0.015, 0.022, 0.006), MOUTH, MISC, sub=1, jitter=0.05)                      # язык
    for v in bm.verts:
        v.co -= V(JAW_PIVOT)
    G.facet(bm, rnd)
    G.uv_pass(bm)
    return bm
