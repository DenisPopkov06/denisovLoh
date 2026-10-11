"""Голова зомби: череп-лицо с глубокими глазницами, светящимися глазами, провалом носа, оскалом и нижняя челюсть.

part_head() / part_jaw() возвращают bmesh в системе части: начало — основание черепа на шее (head) / сустав челюсти (jaw), перёд — −Y.
Кожа — текстура (UV считаются в конце), раны, кости и тени — цвет вершин. Размеры — метры (уже с HEAD_SCALE).

Раскладка по высоте (z от основания черепа, до масштаба): макушка 0.205, надбровье 0.120, глаза 0.086, скулы 0.052, низ носа 0.032,
линия зубов 0.006, подбородок −0.045 — глаза примерно посередине головы, как у настоящего черепа.
"""
import math

import bmesh
from mathutils import Vector

import zombie_geo as G
from zombie_geo import BONE, BONE_DK, DARK, EYE, EYE_COL, GUM, MISC, MOUTH, SKIN, lerp, skin_f

V = Vector
HEAD_SCALE = 1.28
JAW_PIVOT = (0.0, 0.015 * HEAD_SCALE, 0.030 * HEAD_SCALE)       # сустав челюсти в системе головы

# сечения черепа: (z, полуширина, вынос вперёд, вынос назад); перёд −Y
SKULL = [(0.188, 0.020, 0.022, 0.026), (0.178, 0.046, 0.046, 0.060), (0.162, 0.064, 0.070, 0.086), (0.140, 0.076, 0.086, 0.098),
         (0.118, 0.080, 0.092, 0.100), (0.092, 0.080, 0.090, 0.092), (0.062, 0.078, 0.086, 0.086), (0.034, 0.062, 0.080, 0.068),
         (0.008, 0.048, 0.070, 0.054)]
SEG_SKULL = 16
EYES = ((-0.035, 0.090), (0.035, 0.090))                         # (x, z) глазниц


def _skull_ring(z, rx, rf, rb, n=2.3):
    pts = []
    for k in range(SEG_SKULL):
        t = k * math.tau / SEG_SKULL
        c, s = math.cos(t), math.sin(t)
        c = math.copysign(abs(c) ** (2.0 / n), c)
        s = math.copysign(abs(s) ** (2.0 / n), s)
        pts.append(V((rx * c, -s * (rf if s > 0 else rb), z)))
    return pts


def skull_color(p):
    """Череп: кожа, на лбу и висках проплешины до кости, вокруг глазниц и в щеках — тени."""
    x, y, z = p
    c = skin_f(p, 3)
    t = G.noise(x * 2.4, y * 2.0, z * 2.8, 11)
    if t > 0.55 and z > 0.11:
        c = G.mix(c, (1.0, 0.96, 0.82), (t - 0.55) * 3)
    if y < -0.04:
        for ex, ez in EYES:
            d = math.hypot(x - ex, z - ez)
            c = tuple(v * (1.0 - 0.55 * math.exp(-(d / 0.032) ** 2)) for v in c)           # тёмные круги под глазами
        sh = math.exp(-(math.hypot(abs(x) - 0.052, z - 0.030) / 0.026) ** 2)
        c = tuple(v * (1.0 - 0.40 * sh) for v in c)                                         # впалые щёки темнее
    return c


def part_head(rnd):
    bm = bmesh.new()
    rings = [_skull_ring(*r) for r in SKULL]
    faces, rv = G.bridge(bm, rings, SKIN, skull_color, rnd, caps=(True, True))
    verts = list({v for r in rv for v in r})

    # ---- рельеф лица (вмятины и выпуклости, симметрично)
    for sx in (-1, 1):
        G.dent(verts, (sx * 0.035, -0.092, 0.090), 0.030, 0.038, (0, 1, 0))                      # глазницы
        G.dent(verts, (sx * 0.038, -0.094, 0.124), 0.032, -0.015, (0, 1, 0))                     # надбровная дуга
        G.dent(verts, (sx * 0.068, -0.068, 0.058), 0.024, -0.021, (sx * 0.6, 1, 0))              # скула
        G.dent(verts, (sx * 0.082, -0.040, 0.066), 0.020, -0.012, (sx, 0.4, 0))                  # скуловая дуга к уху
        G.dent(verts, (sx * 0.050, -0.062, 0.028), 0.024, 0.026, (-sx * 0.7, 0.8, 0))            # впалая щека
        G.dent(verts, (sx * 0.086, -0.035, 0.112), 0.028, 0.018, (-sx, 0, 0))                    # висок
    G.dent(verts, (0, -0.092, 0.040), 0.017, 0.024, (0, 1, 0))                                   # провал носа
    G.dent(verts, (0, -0.097, 0.108), 0.020, -0.012, (0, 1, 0))                                  # переносица, межбровье
    G.dent(verts, (0, -0.100, 0.160), 0.040, 0.012, (0, 1, 0))                                   # лоб скошен
    G.jitter_verts(verts, rnd, 0.0030)

    # ---- глазницы и ноздри — резкий край (inset) и тёмное дно
    def pick(cx, cz, r, ymax=-0.045):
        return [f for f in bm.faces if (lambda c: c.y < ymax and (c.x - cx) ** 2 + (c.z - cz) ** 2 < r * r)(f.calc_center_median())]

    for cx, cz, r, th, dp in ((-0.035, 0.090, 0.026, 0.0045, 0.026), (0.035, 0.090, 0.026, 0.0045, 0.026),
                              (-0.008, 0.034, 0.0085, 0.002, 0.014), (0.008, 0.034, 0.0085, 0.002, 0.014)):
        sel = pick(cx, cz, r)
        if sel:
            bmesh.ops.inset_region(bm, faces=sel, thickness=th, depth=-dp, use_even_offset=True)
            G.paint(bm, sel, DARK, rnd, SKIN, 0.0)

    # ---- глаза: светящиеся белёсые шарики глубоко в глазницах; уши
    for sx in (-1, 1):
        G.blob(bm, rnd, (sx * 0.035, -0.050, 0.090), (0.0120, 0.0100, 0.0120), EYE_COL, EYE, sub=1, jitter=0.0)
        G.blob(bm, rnd, (sx * 0.083, 0.012, 0.056), (0.0085, 0.020, 0.030), lambda p: skin_f(p, 5), SKIN, sub=1, jitter=0.14,
               rot=(0, 0, sx * 0.45))

    for sx in (-1, 1):                                                                                                         # ноздри — тёмный провал
        G.blob(bm, rnd, (sx * 0.0085, -0.064, 0.040), (0.0085, 0.010, 0.017), DARK, MISC, sub=1, jitter=0.0, rot=(0, 0, sx * 0.25))
    G.tube(bm, rnd, [V((0, -0.093, 0.098)), V((0, -0.100, 0.072)), V((0, -0.098, 0.052))], [(0.0055, 0.0075), (0.0065, 0.0085), (0.0050, 0.0070)],
           5, SKIN, lambda p: skin_f(p, 7), caps=(True, True))                                                                 # спинка носа
    G.blob(bm, rnd, (0, -0.030, 0.000), (0.040, 0.040, 0.020), DARK, MISC, sub=1, jitter=0.04)                                  # тёмная полость рта

    # ---- верхние зубы и дёсны
    arc = [V((0.045 * math.sin(t), -0.012 - 0.064 * math.cos(t), 0.008)) for t in [(-1.1 + 2.2 * i / 14) for i in range(15)]]
    G.tube(bm, rnd, arc, [(0.0045, 0.0055)] * len(arc), 5, MISC, GUM, up=(0, 0, 1), caps=(True, True))
    teeth_arc(bm, rnd, (0, -0.012, 0.008), 0.043, 0.062, 8, -1.05, 1.05, 0.026, True)

    # ---- шея внутри черепа (стык с шеей туловища)
    G.tube(bm, rnd, [V((0, 0.012, 0.015)), V((0, 0.014, -0.050))], [(0.034, 0.036)] * 2, 8, SKIN, lambda p: skin_f(p, 2),
           caps=(False, True))
    bmesh.ops.scale(bm, vec=(HEAD_SCALE,) * 3, verts=bm.verts)
    G.facet(bm, rnd)
    G.uv_pass(bm)
    return bm


def teeth_arc(bm, rnd, c, rx, ry, n, a0, a1, h, upper):
    """Ряд зубов по дуге эллипса (перёд — −Y): неровные, цвета старой слоновой кости; upper — корни сверху."""
    for i in range(n):
        t = a0 + (a1 - a0) * (i + 0.5) / n
        x = c[0] + rx * math.sin(t)
        y = c[1] - ry * math.cos(t)
        k = 1.15 if i in (1, n - 2) else 1.0                                            # клыки чуть длиннее
        hh = h * k * rnd.uniform(0.8, 1.15)
        w = 0.0135 if abs(t) < 0.5 else 0.0120
        col = G.mix(BONE, BONE_DK, rnd.uniform(0.0, 0.5))
        sgn = -1 if upper else 1
        G.box(bm, rnd, (x, y, c[2] + sgn * (hh / 2 - 0.001)), (w, 0.0065, hh), col,
              rot=(math.pi if upper else 0.0, rnd.uniform(-0.12, 0.12), -t), taper=(0.7, 0.8))


def part_jaw(rnd):
    """Нижняя челюсть: U-образная кость, ряд зубов, тёмный язык. Шарнир — у ушей; подбородок на z ≈ −0.075 от шарнира."""
    bm = bmesh.new()
    path = [V(p) for p in ((-0.052, 0.006, 0.026), (-0.050, 0.004, -0.030), (-0.042, -0.026, -0.050), (-0.024, -0.058, -0.054),
                           (-0.007, -0.078, -0.054))]
    path += [V((-p.x, p.y, p.z)) for p in reversed(path)]
    rad = [(0.012, 0.012), (0.019, 0.013), (0.020, 0.013), (0.020, 0.012), (0.021, 0.012)]
    rad += list(reversed(rad))
    G.tube(bm, rnd, path, rad, 6, SKIN, lambda p: skin_f(p, 4), up=(0, 0, 1), caps=(True, True), jit=0.08)
    teeth_arc(bm, rnd, (0, -0.004, -0.034), 0.030, 0.056, 8, -1.0, 1.0, 0.022, False)
    G.tube(bm, rnd, [V((-0.030, -0.050, -0.035)), V((0, -0.062, -0.035)), V((0.030, -0.050, -0.035))], [(0.006, 0.006)] * 3, 5, MISC, GUM,
           caps=(True, True))
    G.blob(bm, rnd, (0, -0.034, -0.033), (0.019, 0.028, 0.008), MOUTH, MISC, sub=1, jitter=0.05)               # язык
    bmesh.ops.scale(bm, vec=(HEAD_SCALE,) * 3, verts=bm.verts)
    G.facet(bm, rnd)
    G.uv_pass(bm)
    return bm
