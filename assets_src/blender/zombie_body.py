"""Тело зомби (по листу «Тело зомби — ракурсы»): жилистый скелетообразный силуэт, рваный жилет с воротником и шипастыми наплечниками,
красно-бурые шорты до колена с большими разрывами и заплатами, широкий ремень с квадратной пряжкой, огромные коленные чашки,
массивные ботинки с манжетным кольцом, кожаные браслеты и большие когтистые кисти.

part_*() возвращают bmesh в системе части: начало — шарнир, конечности свисают вниз по −Z, перёд — −Y (в glTF +Z),
«левая» сторона — +X. Размеры — метры (рост стоя ≈ 1.8 м; в позе сутулый ≈ 1.65 м).
Кожа и ткань — текстуры (UV — в конце), раны, кости, оттенки и тени — цвет вершин (AO запекается в zombie_lib).
"""
import math

import bmesh
from mathutils import Vector

import zombie_geo as G
from zombie_geo import (BONE, BONE_DK, CLOTH, DARK, GUM, LEATHER, METAL, MISC, SKIN, TINT_GREY, TINT_RED, cloth_f, delete_faces,
                        fringe, interp, lerp, skin_f, sx_point)

V = Vector
LIGHT = lambda p: tuple(c * 1.10 for c in skin_f(p, 3))           # выступающие кости под кожей — чуть светлее


def cloth_c(p, k, tint, base=1.0):
    """Цвет ткани: пятна cloth_f × оттенок tint."""
    return tuple(c * t for c, t in zip(cloth_f(p, k, base), tint))


def mirror_x(bm):
    """Зеркало по X (для правой стороны): координаты и обход граней."""
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))


def ragged(verts, rnd, amp):
    """Рваная кромка: вершины нижнего кольца сдвигаются по Z вразнобой."""
    for v in verts:
        v.co.z += rnd.uniform(-amp, amp * 0.4)


def spike(bm, rnd, a, b, r0, r1, color, seg=4, mi=MISC):
    return G.spike(bm, rnd, a, b, r0, r1, color, seg, mi)


def surface_patch(bm, rnd, surf, cx, cz, w, h, tilt, color, off, mi=CLOTH, n=5):
    """Заплата-сетка n×n, повторяющая изгиб поверхности: surf(x, z) → y поверхности; off — отступ по Y (знак — наружу)."""
    ct, st = math.cos(tilt), math.sin(tilt)
    rows = []
    for j in range(n):
        v = -h / 2 + h * j / (n - 1)
        row = []
        for i in range(n):
            u = -w / 2 + w * i / (n - 1)
            x, z = cx + u * ct - v * st, cz + u * st + v * ct
            row.append(V((x, surf(x, z) + off, z)))
        rows.append(row)
    return G.bridge(bm, rows, mi, color, rnd, caps=(False, False), closed=False, jit=0.05)


# ============================================================================ туловище (шарнир — поясница; вверх по +Z)
CHEST = [(-0.04, 0.074, 0.100, 0.000), (0.04, 0.074, 0.104, 0.000), (0.13, 0.082, 0.114, 0.000), (0.22, 0.092, 0.130, 0.000),
         (0.31, 0.098, 0.146, 0.000), (0.37, 0.094, 0.150, 0.000), (0.41, 0.082, 0.132, 0.004), (0.44, 0.060, 0.082, 0.008),
         (0.465, 0.043, 0.050, 0.010)]
TORSO_Z = 0.88                                  # торс сжат по вертикали (у референса короткий сутулый корпус)
NECK_Z = 0.575 * TORSO_Z                                  # шарнир головы в системе туловища
SHOULDER = (0.172, 0.0, 0.385 * TORSO_Z)                  # шарнир плеча (левое; правое — зеркально)


def chest_ab(z, extra=0.0):
    _, a, b, yc = interp(CHEST, z)
    return a + extra, b + extra, yc


def front_y(z, x, extra=0.0, n=2.4):
    """Y поверхности груди (спереди) на высоте z при заданном x."""
    a, b, yc = chest_ab(z, extra)
    k = max(0.0, 1.0 - (abs(x) / b) ** n)
    return yc - a * k ** (1.0 / n)


def part_chest(rnd):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 2)
    pts = [V((0, yc, z)) for z, a, b, yc in CHEST]
    G.tube(bm, rnd, pts, [(a, b) for z, a, b, yc in CHEST], 14, SKIN, skin, up=(0, -1, 0), caps=(True, True), n=2.4, jit=0.012)
    # ---- ключицы, грудина, рёбра: выступают из-под порванной рубашки
    for sx in (-1, 1):
        G.tube(bm, rnd, [V((sx * 0.008, -0.056, 0.440)), V((sx * 0.08, -0.060, 0.446)), V((sx * 0.162, -0.040, 0.425))],
               [0.0085, 0.0095, 0.0085], 5, SKIN, LIGHT, caps=(True, True))
        for z0 in (0.285, 0.322, 0.358, 0.392):                                       # рёбра: дуга от грудины к боку
            pr = []
            for t in (0.10, 0.45, 0.80, 1.05):
                x = sx * (0.012 + 0.126 * t)
                z = z0 - 0.058 * t * t
                pr.append(V((x, front_y(z, x, 0.0035), z)))
            G.tube(bm, rnd, pr, [0.0062, 0.0070, 0.0070, 0.0060], 5, SKIN, LIGHT, caps=(True, True))
        G.blob(bm, rnd, (sx * SHOULDER[0], 0, SHOULDER[2] + 0.015), (0.050, 0.046, 0.046), skin, SKIN, jitter=0.08)    # плечевой сустав
        G.blob(bm, rnd, (sx * 0.075, 0.006, 0.438), (0.055, 0.042, 0.026), skin, SKIN, jitter=0.08)                     # трапеция
    G.tube(bm, rnd, [V((0, front_y(z, 0, 0.003), z)) for z in (0.26, 0.33, 0.40, 0.435)], [(0.006, 0.011)] * 4, 5, SKIN, LIGHT,
           up=(0, -1, 0), caps=(True, True))                                                                              # грудина
    # ---- шея с сухожилиями
    G.tube(bm, rnd, [V((0, 0.012, 0.44)), V((0, 0.010, 0.52)), V((0, 0.010, 0.600))], [(0.036, 0.036), (0.033, 0.033), (0.031, 0.031)], 8,
           SKIN, lambda p: skin_f(p, 4), up=(0, -1, 0), caps=(False, True), jit=0.03)
    for sx in (-1, 1):
        G.tube(bm, rnd, [V((sx * 0.030, -0.006, 0.570)), V((sx * 0.020, -0.030, 0.510)), V((sx * 0.010, -0.040, 0.458))],
               [0.0075, 0.0085, 0.0075], 5, SKIN, LIGHT, caps=(True, True))
    # ---- нательная рубашка: серо-коричневая, порвана V-вырезом и дырами, бахрома на подоле
    zs = [-0.05, 0.02, 0.10, 0.20, 0.29, 0.36, 0.415, 0.445]
    seg = 16
    rings = []
    for z in zs:
        a, b, yc = chest_ab(z, 0.011)
        rings.append([V((sx_point(a, b, k * math.tau / seg)[0], yc + sx_point(a, b, k * math.tau / seg)[1], z)) for k in range(seg)])
    shirt = lambda p: cloth_c(p, 6, (0.74, 0.74, 0.78), 0.80)
    faces, rv = G.bridge(bm, rings, CLOTH, shirt, rnd, caps=(False, False), closed=True, jit=0.09)
    delete_faces(bm, lambda c: c.y < -0.04 and c.z > 0.17 and abs(c.x) < 0.012 + (c.z - 0.17) * 0.40)            # V-вырез
    delete_faces(bm, lambda c: c.y < -0.07 and 0.07 < c.z < 0.15 and 0.03 < c.x < 0.10)                           # дыра на животе
    delete_faces(bm, lambda c: c.y > 0.05 and 0.12 < c.z < 0.22 and -0.09 < c.x < -0.02)                          # дыра на спине
    hem = [v.co.copy() for v in rv[0]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0.05, -1), 0.03, 0.10, lambda p: tuple(c * 0.9 for c in shirt(p)), per=1, center=V((0, 0, -0.05)))
    # ---- жилет: серо-коричневый спереди, красно-бурый сзади; открытый перед, лацканы, проймы, длинная рваная бахрома на спине
    VEST = [(-0.03, 0.112, 0.130), (0.04, 0.104, 0.124), (0.11, 0.108, 0.130), (0.21, 0.118, 0.148), (0.31, 0.126, 0.166),
            (0.385, 0.120, 0.176), (0.43, 0.098, 0.146), (0.466, 0.068, 0.088), (0.490, 0.056, 0.064)]
    TH0 = [0.32, 0.32, 0.40, 0.50, 0.58, 0.72, 0.98, 1.20, 1.40]                 # половина раскрытия спереди (рад) по высоте
    seg = 17
    rings = []
    for (z, a, b), th0 in zip(VEST, TH0):
        row = []
        for k in range(seg):
            th = th0 + (math.tau - 2 * th0) * k / (seg - 1)
            x, y = sx_point(a, b, th)
            row.append(V((x, y, z)))
        rings.append(row)

    def vest(p):
        t = G.smooth(-0.01, 0.07, p[1])
        tint = tuple(lerp(TINT_GREY[i], TINT_RED[i], t) for i in range(3))
        f = 0.74 + 0.30 * G.smooth(-0.12, 0.30, p[2])
        return tuple(c * f for c in cloth_c(p, 8, tint, 1.12))

    faces, rv = G.bridge(bm, rings, CLOTH, vest, rnd, caps=(False, False), closed=False, jit=0.08)
    delete_faces(bm, lambda c: abs(c.x) > 0.150 and 0.30 < c.z < 0.425 and abs(c.y) < 0.09)                          # проймы
    delete_faces(bm, lambda c: c.y > 0.07 and 0.02 < c.z < 0.10 and 0.02 < c.x < 0.08)                              # дыра на спине
    delete_faces(bm, lambda c: c.y > 0.07 and 0.10 < c.z < 0.20 and -0.05 < c.x < -0.02)                            # вертикальный разрыв
    for idx in (0, -1):                                                                                             # лацканы
        prev = None
        for i, row in enumerate(rv[:-3]):
            v = row[idx]
            w = (0.020 + 0.040 * G.smooth(0.0, 0.40, VEST[i][0])) if VEST[i][0] > -0.02 else 0.012
            nv = bm.verts.new(v.co + V(((1 if v.co.x > 0 else -1) * w, -0.022, 0.004)))
            if prev is not None:
                f = bm.faces.new((prev[0], v, nv, prev[1]))
                G.paint(bm, [f], lambda p: cloth_c(p, 9, TINT_GREY, 1.0), rnd, CLOTH, 0.08)
            prev = (v, nv)
    ragged(rv[0], rnd, 0.035)
    hem_all = [v.co.copy() for v in rv[0]]
    n = len(hem_all)
    fringe(bm, rnd, hem_all[:5], (0, 0.04, -1), 0.03, 0.10, lambda p: cloth_c(p, 10, TINT_GREY, 0.85), per=1, center=V((0, 0, -0.04)))
    fringe(bm, rnd, hem_all[n - 5:], (0, 0.04, -1), 0.03, 0.10, lambda p: cloth_c(p, 10, TINT_GREY, 0.85), per=1, center=V((0, 0, -0.04)))
    fringe(bm, rnd, hem_all[4:n - 4], (0, 0.18, -1), 0.07, 0.22, lambda p: cloth_c(p, 10, TINT_RED, 0.85), per=2, center=V((0, 0, -0.04)),
           flare=0.02, wob=0.5)                                                                                     # длинные лохмотья на спине
    # V-образный клин (кокетка) на спине: сетка, прижатая к поверхности жилета
    def vest_back_y(x, z):
        _, a, b = interp(VEST, z)
        return a * max(0.0, 1.0 - (abs(x) / b) ** 2.4) ** (1.0 / 2.4)

    yoke = []
    for zz in (0.405, 0.345, 0.285, 0.225):
        w = 0.115 * (zz - 0.205) / 0.200 + 0.012
        yoke.append([V((-w + 2 * w * k / 4, vest_back_y(-w + 2 * w * k / 4, zz) + 0.004, zz)) for k in range(5)])
    G.bridge(bm, yoke, CLOTH, lambda p: cloth_c(p, 12, (1.0, 0.76, 0.70), 1.15), rnd, caps=(False, False), closed=False, jit=0.06)
    # воротник-стойка: высокий сзади, рваный верх
    top_rings = []
    for first in (True, False):
        row = []
        for k in range(13):
            th = 0.50 + (math.tau - 1.0) * k / 12
            r = 0.060 if first else 0.072
            x, y = sx_point(r, r + 0.004, th, 2.0)
            z = 0.452 if first else 0.500 + 0.078 * (0.5 - 0.5 * math.cos(th)) + rnd.uniform(-0.010, 0.006)
            row.append(V((x, 0.012 + y, z)))
        top_rings.append(row)
    G.bridge(bm, top_rings, CLOTH, lambda p: cloth_c(p, 11, (0.78, 0.76, 0.80), 0.95), rnd, closed=False, jit=0.07)
    rings = []                                                                                                      # воротник рубашки с острыми концами
    for z, r in ((0.462, 0.056), (0.514, 0.068)):
        rings.append([V((sx_point(r, r, th, 2.0)[0], 0.012 + sx_point(r, r, th, 2.0)[1], z))
                      for th in [0.55 + (math.tau - 1.10) * k / 10 for k in range(11)]])
    faces, rv2 = G.bridge(bm, rings, CLOTH, lambda p: cloth_c(p, 31, (0.62, 0.62, 0.66), 0.8), rnd, caps=(False, False), closed=False, jit=0.06)
    for idx, sgn in ((0, 1), (-1, -1)):
        vb, vt = rv2[0][idx], rv2[1][idx]
        f = bm.faces.new((vb, vt, bm.verts.new(vt.co + V((sgn * 0.024, -0.030, -0.044)))))
        G.paint(bm, [f], lambda p: cloth_c(p, 32, (0.62, 0.62, 0.66), 0.8), rnd, CLOTH, 0.08)
    # рваный воротник-пелерина вокруг шеи: тёмный сине-серый, длинная бахрома по плечам (как на листе головы)
    cape = [(0.488, 0.062, 0.070), (0.462, 0.086, 0.106), (0.436, 0.108, 0.150), (0.408, 0.122, 0.178)]
    rings = []
    for z, a, b in cape:
        row = []
        for k in range(15):
            th = 0.60 + (math.tau - 1.2) * k / 14
            x, y = sx_point(a, b, th)
            row.append(V((x, 0.012 + y, z)))
        rings.append(row)
    cape_col = lambda p: cloth_c(p, 61, (0.64, 0.66, 0.78), 0.78)
    faces, rv3 = G.bridge(bm, rings, CLOTH, cape_col, rnd, caps=(False, False), closed=False, jit=0.08)
    ragged(rv3[-1], rnd, 0.02)
    fringe(bm, rnd, [v.co.copy() for v in rv3[-1]], (0, 0.0, -1), 0.04, 0.11, lambda p: cloth_c(p, 62, (0.60, 0.62, 0.74), 0.72), per=2,
           center=V((0, 0.012, 0.40)), flare=0.012, wob=0.6)
    for (px, pz, pw, ph, tilt) in ((-0.07, 0.17, 0.075, 0.085, 0.10), (0.06, 0.27, 0.060, 0.070, -0.12)):             # заплатки на спине
        surface_patch(bm, rnd, vest_back_y, px, pz, pw * 1.14, ph * 1.14, tilt, lambda p: cloth_c(p, 22, TINT_RED, 0.55), 0.0030)       # обшивка
        surface_patch(bm, rnd, vest_back_y, px, pz, pw, ph, tilt, lambda p: cloth_c(p, 21, (1.0, 0.82, 0.74), 1.25), 0.0055)              # заплата
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    bmesh.ops.scale(bm, vec=(1.0, 1.0, TORSO_Z), verts=bm.verts)
    G.uv_pass(bm)
    return bm


# ============================================================================ таз: шорты и ремень (шарнир — центр таза)
PELVIS = [(-0.13, 0.074, 0.100), (-0.06, 0.090, 0.126), (0.02, 0.086, 0.122), (0.09, 0.080, 0.112)]
HIP = (0.092, 0.0, -0.07)                       # шарнир бедра (левое)


def part_pelvis(rnd):
    bm = bmesh.new()
    shorts = lambda p: cloth_c(p, 12, TINT_RED, 0.95)
    seg = 14
    rings = []
    for z, a, b in PELVIS:
        rings.append([V((sx_point(a + 0.014, b + 0.014, k * math.tau / seg)[0], sx_point(a + 0.014, b + 0.014, k * math.tau / seg)[1], z))
                      for k in range(seg)])
    G.bridge(bm, rings, CLOTH, shorts, rnd, caps=(False, False), closed=True, jit=0.08)
    # широкий ремень с квадратной пряжкой, свисающим концом и шлёвками
    belt = []
    for z in (0.055, 0.115):
        belt.append([V((sx_point(0.100, 0.132, k * math.tau / seg)[0], sx_point(0.100, 0.132, k * math.tau / seg)[1], z)) for k in range(seg)])
    G.bridge(bm, belt, CLOTH, lambda p: cloth_c(p, 13, (0.45, 0.36, 0.32), 0.7), rnd, caps=(False, False), closed=True, jit=0.05)
    G.box(bm, rnd, (0, -0.103, 0.085), (0.066, 0.012, 0.062), METAL)                                                # пряжка: рамка
    G.box(bm, rnd, (0, -0.1105, 0.085), (0.042, 0.008, 0.038), LEATHER)                                             # и вырез под ремень
    G.box(bm, rnd, (0.0, -0.1125, 0.085), (0.006, 0.006, 0.042), METAL)                                             # язычок
    G.box(bm, rnd, (0.060, -0.098, 0.026), (0.018, 0.005, 0.130), LEATHER, rot=(0.05, 0, 0.12))                     # свисающий конец ремня
    for k in (-3, -2, 2, 3):                                                                                       # шлёвки
        th = k * 0.36
        x, y = sx_point(0.106, 0.138, th)
        G.box(bm, rnd, (x, y, 0.085), (0.014, 0.008, 0.062), LEATHER, rot=(0, 0, -th))
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


# ============================================================================ руки (шарнир — плечо / локоть / запястье; вниз по −Z)
UPPER_LEN, FORE_LEN = 0.305, 0.272
UPPER = [(z, a * 1.16, b * 1.16) for z, a, b in [(0.0, 0.046, 0.046), (-0.06, 0.037, 0.038), (-0.14, 0.031, 0.032), (-0.22, 0.030, 0.031), (-UPPER_LEN, 0.033, 0.034)]]
FORE = [(z, a * 1.16, b * 1.16) for z, a, b in [(0.0, 0.034, 0.036), (-0.06, 0.029, 0.033), (-0.14, 0.025, 0.028), (-0.21, 0.020, 0.025), (-FORE_LEN, 0.019, 0.024)]]


def part_upper_arm(rnd, side):
    """Плечо с рваным наплечником-рукавом (торчащие шипы вверх и наружу); side=+1 — левое (+X), −1 — правое."""
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 20 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in UPPER], [(a, b) for z, a, b in UPPER], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0.002, -UPPER_LEN), (0.044, 0.044, 0.044), skin, SKIN, jitter=0.08)                              # локоть — костлявый
    sl = [(0.074, 0.036, 0.036), (0.060, 0.064, 0.062), (0.020, 0.080, 0.078), (-0.04, 0.076, 0.074), (-0.10, 0.076, 0.074), (-0.150, 0.082, 0.080)]
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 9, rnd=rnd, jit=0.03) for z, a, b in sl]
    sleeve = lambda p: cloth_c(p, 14 + side, TINT_GREY, 1.0)
    faces, rv = G.bridge(bm, rings, CLOTH, sleeve, rnd, caps=(True, False), closed=True, jit=0.08)
    ragged(rv[-1], rnd, 0.04)
    hem = [v.co.copy() for v in rv[-1]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0.0, -1), 0.05, 0.14, lambda p: cloth_c(p, 16, TINT_GREY, 0.9), per=1, center=V((0, 0, -0.150)))
    for a_, b_ in (((0.045, 0.0, 0.070), (0.092, 0.010, 0.098)), ((0.030, 0.056, 0.062), (0.060, 0.092, 0.090)),
                   ((0.036, -0.050, 0.064), (0.072, -0.074, 0.092)), ((0.0, 0.060, 0.070), (-0.006, 0.100, 0.100))):    # шипы наплечника
        spike(bm, rnd, V((side * a_[0], a_[1], a_[2])), V((side * b_[0], b_[1], b_[2])), 0.014, 0.003,
              lambda p: cloth_c(p, 17, TINT_GREY, 1.0), 4, CLOTH)
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


def part_forearm(rnd, side):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 24 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in FORE], [(a, b) for z, a, b in FORE], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0.003, 0.0), (0.044, 0.044, 0.040), skin, SKIN, jitter=0.08)                                     # локоть
    G.blob(bm, rnd, (0, 0.034, -0.006), (0.022, 0.020, 0.026), LIGHT, SKIN, jitter=0.10)                                 # локтевой отросток
    G.tube(bm, rnd, [V((0, 0.029, -0.04)), V((0, 0.027, -0.14)), V((0, 0.024, -0.232))], [0.0075, 0.0070, 0.0062], 5, SKIN, LIGHT, caps=(True, True))
    G.tube(bm, rnd, [V((-0.022, -0.020, -0.05)), V((-0.020, -0.018, -0.14)), V((-0.018, -0.014, -0.225))], [0.0062, 0.0058, 0.0050], 5, SKIN, LIGHT,
           caps=(True, True))
    for sx in (-1, 1):                                                                                                    # косточки запястья
        G.blob(bm, rnd, (sx * 0.021, 0.010, -0.244), (0.0115, 0.0115, 0.0115), LIGHT, SKIN, jitter=0.10)
    rings = []                                                                                                           # широкий кожаный браслет — плотно по предплечью
    for z, dr in ((-0.186, 0.002), (-0.192, 0.007), (-0.232, 0.007), (-0.238, 0.002)):
        fa, fb = interp(FORE, z)[1:3]
        rings.append(G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), fa + dr, fb + dr, 9, rnd=rnd))
    G.bridge(bm, rings, CLOTH, lambda p: cloth_c(p, 25, (0.70, 0.46, 0.40), 0.7), rnd, caps=(False, False), closed=True)
    G.box(bm, rnd, (0.0, -(interp(FORE, -0.212)[1] + 0.008), -0.212), (0.026, 0.008, 0.034), METAL)
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


FINGERS = [(-0.028, (0.038, 0.026, 0.021), 0.20), (-0.010, (0.042, 0.028, 0.022), 0.30), (0.008, (0.038, 0.026, 0.020), 0.40),
           (0.025, (0.031, 0.021, 0.018), 0.50)]


def part_hand(rnd, side):
    """Кисть левая (ладонь смотрит на −X, большой палец вперёд −Y); правая — зеркало. Большая, с длинными скрюченными пальцами и когтями."""
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 28)
    palm = [(0.0, 0.015, 0.026), (-0.02, 0.014, 0.034), (-0.055, 0.0125, 0.040), (-0.088, 0.0115, 0.042)]
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in palm], [(a, b) for z, a, b in palm], 8, SKIN, skin, up=(1, 0, 0), caps=(True, True), jit=0.04)
    for fy, lens, c0 in FINGERS:
        G.blob(bm, rnd, (0.011, fy, -0.088), (0.0105, 0.0105, 0.0115), skin, SKIN, jitter=0.08)                         # костяшка
        G.tube(bm, rnd, [V((0.012, fy * 0.5, -0.012)), V((0.012, fy, -0.088))], [0.0036, 0.0036], 4, SKIN, LIGHT, caps=(True, True))   # сухожилие
        p = V((0, fy, -0.090))
        pts, ang = [p.copy()], [c0, c0 + 0.38, c0 + 0.78]
        for ln, th in zip(lens, ang):
            p = p + V((-math.sin(th), fy * 0.10, -math.cos(th))).normalized() * ln
            pts.append(p.copy())
        G.tube(bm, rnd, pts, [0.0090, 0.0080, 0.0068, 0.0054], 5, SKIN, skin, caps=(True, True), up=(1, 0, 0))
        for q in pts[1:3]:
            G.blob(bm, rnd, q, (0.0080, 0.0080, 0.0080), skin, SKIN, sub=1, jitter=0.06)
        d = (pts[-1] - pts[-2]).normalized()
        G.spike(bm, rnd, pts[-1] - d * 0.002, pts[-1] + d * 0.014, 0.0052, 0.0014, BONE_DK, seg=4)                       # коготь
    tp = [V((-0.008, -0.030, -0.024)), V((-0.024, -0.050, -0.060)), V((-0.034, -0.052, -0.092))]
    G.tube(bm, rnd, tp, [0.0120, 0.0095, 0.0072], 5, SKIN, skin, caps=(True, True), up=(1, 0, 0))
    G.spike(bm, rnd, tp[-1] - V((0, 0, 0.002)), tp[-1] + V((-0.004, 0.0, -0.014)), 0.0054, 0.0014, BONE_DK, seg=4)
    bmesh.ops.scale(bm, vec=(1.45, 1.45, 1.45), verts=bm.verts)
    if side < 0:
        mirror_x(bm)
    G.uv_pass(bm)
    return bm


# ============================================================================ ноги (шарнир — бедро / колено / лодыжка; вниз по −Z)
THIGH_LEN, SHIN_LEN, ANKLE_H = 0.42, 0.45, 0.09
SHIN_D = SHIN_LEN - 0.38                       # на сколько голень длиннее базовой (все детали голенища сдвинуты вниз)
THIGH = [(z * THIGH_LEN / 0.41, a * 1.06, b * 1.06) for z, a, b in [(0.0, 0.070, 0.072), (-0.10, 0.064, 0.066), (-0.22, 0.052, 0.055), (-0.32, 0.044, 0.046), (-0.41, 0.040, 0.042)]]
SHIN = [(z * SHIN_LEN / 0.38, a * 1.10, b * 1.10) for z, a, b in [(0.0, 0.042, 0.044), (-0.06, 0.038, 0.040), (-0.16, 0.031, 0.032), (-0.27, 0.026, 0.028), (-0.38, 0.028, 0.030)]]


def part_thigh(rnd, side):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 30 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in THIGH], [(a, b) for z, a, b in THIGH], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0, 0.0), (0.072, 0.072, 0.062), skin, SKIN, jitter=0.08)                                          # тазобедренный сустав
    for sx in (-1, 1):
        G.blob(bm, rnd, (sx * 0.030, 0.004, -THIGH_LEN + 0.002), (0.022, 0.026, 0.028), skin, SKIN, jitter=0.08)           # мыщелки
    # шорты до колена: свободные, расширяются книзу, большие рваные клинья, заплата спереди
    sh = [(0.045, 0.094, 0.096), (-0.05, 0.098, 0.100), (-0.15, 0.106, 0.110), (-0.255, 0.116, 0.120)]
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 11, rnd=rnd, jit=0.03) for z, a, b in sh]
    shorts = lambda p: cloth_c(p, 34 + side, TINT_RED, 0.95)
    faces, rv = G.bridge(bm, rings, CLOTH, shorts, rnd, caps=(False, False), closed=True, jit=0.08)
    ragged(rv[-1], rnd, 0.05)
    hem = [v.co.copy() for v in rv[-1]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0, -1), 0.04, 0.13, lambda p: cloth_c(p, 36, TINT_RED, 0.85), per=1, center=V((0, 0, -0.255)), flare=0.014, wob=0.6)
    def thigh_front_y(x, z):                                                                                              # передняя поверхность шорт на бедре
        _, a_, b_ = interp(sh, z)
        return -a_ * max(0.0, 1.0 - (x / b_) ** 2) ** 0.5

    surface_patch(bm, rnd, thigh_front_y, 0.02 * side, -0.12, 0.092, 0.100, 0.10, lambda p: cloth_c(p, 40 + side, TINT_RED, 0.5), -0.0030)           # обшивка
    surface_patch(bm, rnd, thigh_front_y, 0.02 * side, -0.12, 0.080, 0.088, 0.10, lambda p: cloth_c(p, 38 + side, (1.0, 0.84, 0.76), 1.3), -0.0055)   # заплата
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


def part_shin(rnd, side):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 40 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in SHIN], [(a, b) for z, a, b in SHIN], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, -0.034, 0.004), (0.052, 0.036, 0.056), LIGHT, SKIN, jitter=0.10)                                  # огромная коленная чашечка
    G.blob(bm, rnd, (0, 0.002, 0.0), (0.046, 0.046, 0.042), skin, SKIN, jitter=0.08)                                      # колено
    G.tube(bm, rnd, [V((0, -0.040, -0.07)), V((0, -0.034, -0.21)), V((0, -0.028, -0.35))], [0.0085, 0.0078, 0.0068], 5, SKIN, LIGHT, caps=(True, True))   # гребень голени
    G.blob(bm, rnd, (0, 0.022, -0.155), (0.032, 0.028, 0.070), skin, SKIN, jitter=0.10)                                    # икра
    # голенище ботинка (кожа), толстое манжетное кольцо с пряжкой, рваная ткань поверх
    boot = lambda p: cloth_c(p, 48 + side, (0.62, 0.50, 0.44), 0.85)
    sh = [(-0.262 - SHIN_D, 0.066, 0.068), (-0.30 - SHIN_D, 0.062, 0.064), (-0.35 - SHIN_D, 0.060, 0.062), (-0.392 - SHIN_D, 0.064, 0.066)]
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 10, rnd=rnd, jit=0.02) for z, a, b in sh]
    G.bridge(bm, rings, CLOTH, boot, rnd, caps=(False, False), closed=True, jit=0.07)
    cuff = [(-0.200 - SHIN_D, 0.074, 0.076), (-0.208 - SHIN_D, 0.083, 0.085), (-0.252 - SHIN_D, 0.083, 0.085), (-0.262 - SHIN_D, 0.074, 0.076)]
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 11, rnd=rnd, jit=0.01) for z, a, b in cuff]
    G.bridge(bm, rings, CLOTH, lambda p: cloth_c(p, 49 + side, (0.58, 0.46, 0.40), 0.8), rnd, caps=(False, False), closed=True, jit=0.06)
    G.box(bm, rnd, (0.0, -0.086, -0.230 - SHIN_D), (0.034, 0.008, 0.040), METAL)                                                    # пряжка кольца
    G.box(bm, rnd, (0.040, -0.085, -0.236 - SHIN_D), (0.020, 0.005, 0.030), LEATHER, rot=(0, 0, 0.2))                               # хвост ремешка
    skirt = [(-0.150 - SHIN_D, 0.052, 0.054), (-0.178 - SHIN_D, 0.066, 0.068), (-0.215 - SHIN_D, 0.086, 0.088)]                                       # рваная ткань поверх манжеты
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 10, rnd=rnd, jit=0.03) for z, a, b in skirt]
    faces, rv = G.bridge(bm, rings, CLOTH, lambda p: cloth_c(p, 50 + side, TINT_RED, 0.75), rnd, caps=(False, False), closed=True, jit=0.08)
    ragged(rv[-1], rnd, 0.03)
    hem = [v.co.copy() for v in rv[-1]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0, -1), 0.03, 0.09, lambda p: cloth_c(p, 51, TINT_RED, 0.7), per=1, center=V((0, 0, -0.215 - SHIN_D)), flare=0.012)
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


FOOT = [(0.092, 0.046, 0.020), (0.058, 0.058, 0.040), (0.0, 0.064, 0.052), (-0.060, 0.066, 0.020), (-0.120, 0.070, -0.004),
        (-0.172, 0.066, -0.020), (-0.208, 0.052, -0.030)]       # y, полуширина, верх (z)
SOLE = 0.028                                                     # толщина подошвы; низ ботинка на z = −ANKLE_H
WELD = 0.010                                                     # на сколько верх ботинка и подошва заходят друг в друга


def part_foot(rnd, side):
    """Массивный ботинок ниже голенища: толстая подошва, каблук, круглый носок, шнуровка; шарнир — лодыжка, подошва на z = −ANKLE_H."""
    bm = bmesh.new()
    boot = lambda p: cloth_c(p, 52 + side, (0.62, 0.50, 0.44), 0.85)
    zb = -ANKLE_H + SOLE - WELD
    pts = [V((0, y, (top + zb) / 2)) for y, w, top in FOOT]
    rad = [((top - zb) / 2, w) for y, w, top in FOOT]
    G.tube(bm, rnd, pts, rad, 10, CLOTH, boot, up=(0, 0, 1), caps=(True, True), n=3.0, jit=0.02)
    G.tube(bm, rnd, [V((0, y, -ANKLE_H + (SOLE + WELD) / 2)) for y, w, top in FOOT], [((SOLE + WELD) / 2, w + 0.004) for y, w, top in FOOT], 8, MISC,
           LEATHER, up=(0, 0, 1), caps=(True, True), n=8.0)
    G.box(bm, rnd, (0, 0.064, -ANKLE_H + 0.012), (0.100, 0.052, 0.030), LEATHER)                                         # каблук
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), 0.075, 0.077, 11, rnd=rnd, jit=0.02) for z in (0.062, -0.018)]
    G.bridge(bm, rings, CLOTH, boot, rnd, caps=(False, False), closed=True, jit=0.06)                                    # манжета-стык с голенищем
    laces = (0.22, 0.17, 0.10)
    for y0 in (-0.012, -0.040, -0.068, -0.096):                                                                          # шнуровка по подъёму
        top = interp([(y, w, t) for y, w, t in FOOT][::-1], y0, 0)[2]
        G.box(bm, rnd, (0, y0, top + 0.003), (0.058, 0.009, 0.006), laces, rot=(0, 0, 0.35 if y0 > -0.05 else -0.35))
        for sx in (-1, 1):
            G.box(bm, rnd, (sx * 0.030, y0, top + 0.002), (0.008, 0.012, 0.007), METAL)                                  # блочки-люверсы
    G.box(bm, rnd, (0, -0.180, -0.040), (0.082, 0.056, 0.036), boot((0.1, 0.1, 0.1)), rot=(0.3, 0, 0), mi=CLOTH)           # носок
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == CLOTH])
    G.uv_pass(bm)
    return bm
