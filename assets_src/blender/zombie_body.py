"""Тело зомби: туловище с рваной рубашкой и жилеткой, таз с шортами, руки с когтистыми кистями, ноги, тяжёлые ботинки.

part_*() возвращают bmesh в системе части: начало — шарнир, конечности свисают вниз по −Z, перёд — −Y (в glTF +Z),
«левая» сторона — +X. Размеры — метры (рост стоя ≈ 1.8 м; в позе сутулый ≈ 1.65 м).
Кожа и ткань — текстуры (UV — в конце), раны, кости и тени — цвет вершин.
"""
import math

import bmesh
from mathutils import Vector

import zombie_geo as G
from zombie_geo import (BONE, BONE_DK, CLOTH, DARK, GUM, METAL, MISC, SKIN, cloth_f, delete_faces, fringe, interp, lerp,
                        skin_f, sx_point)

V = Vector
LIGHT = lambda p: tuple(c * 1.12 for c in skin_f(p, 3))           # выступающие кости под кожей — чуть светлее
LEATHER = (0.030, 0.022, 0.016)                                    # тёмная кожа ремня и подошв


# ============================================================================ туловище (шарнир — поясница; вверх по +Z)
CHEST = [(-0.04, 0.080, 0.116, 0.000), (0.04, 0.078, 0.118, 0.000), (0.13, 0.086, 0.126, 0.000), (0.22, 0.096, 0.142, 0.000),
         (0.31, 0.102, 0.156, 0.000), (0.37, 0.098, 0.158, 0.000), (0.41, 0.084, 0.138, 0.004), (0.44, 0.060, 0.082, 0.008),
         (0.465, 0.043, 0.050, 0.010)]
NECK_Z = 0.575                                   # шарнир головы в системе туловища
SHOULDER = (0.172, 0.0, 0.385)                  # шарнир плеча (левое; правое — зеркально)


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
        G.tube(bm, rnd, [V((sx * 0.008, -0.056, 0.440)), V((sx * 0.08, -0.060, 0.446)), V((sx * 0.165, -0.040, 0.425))],
               [0.0085, 0.0095, 0.0085], 5, SKIN, LIGHT, caps=(True, True))
        for z0 in (0.285, 0.322, 0.358, 0.392):                                       # рёбра: дуга от грудины к боку
            pr = []
            for t in (0.10, 0.45, 0.80, 1.05):
                x = sx * (0.012 + 0.136 * t)
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
    # ---- нательная рубашка: порвана V-вырезом и дырами, бахрома на подоле
    zs = [-0.05, 0.02, 0.10, 0.20, 0.29, 0.36, 0.415, 0.445]
    seg = 16
    rings = []
    for z in zs:
        a, b, yc = chest_ab(z, 0.011)
        rings.append([V((sx_point(a, b, k * math.tau / seg)[0], yc + sx_point(a, b, k * math.tau / seg)[1], z)) for k in range(seg)])
    shirt = lambda p: tuple(c * k for c, k in zip(cloth_f(p, 6, 0.72), (0.92, 0.96, 1.04)))
    faces, rv = G.bridge(bm, rings, CLOTH, shirt, rnd, caps=(False, False), closed=True, jit=0.09)
    delete_faces(bm, lambda c: c.y < -0.04 and c.z > 0.17 and abs(c.x) < 0.012 + (c.z - 0.17) * 0.40)            # V-вырез
    delete_faces(bm, lambda c: c.y < -0.07 and 0.07 < c.z < 0.15 and 0.03 < c.x < 0.10)                           # дыра на животе
    delete_faces(bm, lambda c: c.y > 0.05 and 0.12 < c.z < 0.22 and -0.09 < c.x < -0.02)                          # дыра на спине
    hem = [v.co.copy() for v in rv[0]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0.05, -1), 0.03, 0.10, lambda p: tuple(c * 0.9 for c in shirt(p)), per=1, center=V((0, 0, -0.05)))
    # ---- куртка-жилет: открытый перед, лацканы, рваный подол, воротник, проймы
    VEST = [(-0.04, 0.124, 0.154, 0.0), (0.03, 0.116, 0.148, 0.0), (0.10, 0.120, 0.156, 0.0), (0.20, 0.130, 0.176, 0.0),
            (0.31, 0.140, 0.196, 0.0), (0.385, 0.134, 0.206, 0.002), (0.43, 0.108, 0.168, 0.006), (0.465, 0.074, 0.096, 0.010),
            (0.490, 0.056, 0.064, 0.012)]
    TH0 = [0.30, 0.30, 0.38, 0.46, 0.55, 0.70, 0.95, 1.20, 1.40]                 # половина раскрытия спереди (рад) по высоте
    seg = 15
    rings = []
    for (z, a, b, yc), th0 in zip(VEST, TH0):
        row = []
        for k in range(seg):
            th = th0 + (math.tau - 2 * th0) * k / (seg - 1)
            x, y = sx_point(a, b, th)
            row.append(V((x, yc + y, z)))
        rings.append(row)
    vest = lambda p: tuple(c * (0.74 + 0.30 * G.smooth(-0.12, 0.30, p[2])) for c in cloth_f(p, 8, 1.12))
    faces, rv = G.bridge(bm, rings, CLOTH, vest, rnd, caps=(False, False), closed=False, jit=0.08)
    delete_faces(bm, lambda c: abs(c.x) > 0.150 and 0.30 < c.z < 0.425 and abs(c.y) < 0.09)                          # проймы
    delete_faces(bm, lambda c: c.y > 0.07 and 0.02 < c.z < 0.10 and 0.02 < c.x < 0.08)                              # дыра на спине
    for idx in (0, -1):                                                                                             # лацканы
        prev = None
        for i, row in enumerate(rv[:-3]):
            v = row[idx]
            w = (0.020 + 0.040 * G.smooth(0.0, 0.40, VEST[i][0])) if VEST[i][0] > -0.02 else 0.012
            nv = bm.verts.new(v.co + V(((1 if v.co.x > 0 else -1) * w, -0.022, 0.004)))
            if prev is not None:
                f = bm.faces.new((prev[0], v, nv, prev[1]))
                G.paint(bm, [f], lambda p: cloth_f(p, 9, 0.95), rnd, CLOTH, 0.08)
            prev = (v, nv)
    ragged(rv[0], rnd, 0.03)
    fringe(bm, rnd, [v.co.copy() for v in rv[0]], (0, 0.04, -1), 0.03, 0.13, lambda p: cloth_f(p, 10, 0.80), per=3, center=V((0, 0, -0.04)))
    cr = []
    for z, d in ((0.490, 0.0), (0.545, 0.012)):                                                                      # воротник сзади
        a, b = 0.056 + d, 0.064 + d
        cr.append([V((sx_point(a, b, th)[0], 0.012 + sx_point(a, b, th)[1], z)) for th in [1.55 + (math.tau - 3.10) * k / 8 for k in range(9)]])
    G.bridge(bm, cr, CLOTH, lambda p: cloth_f(p, 11, 0.9), rnd, closed=False)
    rings = []                                                                                                      # воротник рубашки с острыми концами
    for z, r in ((0.462, 0.056), (0.514, 0.068)):
        rings.append([V((sx_point(r, r, th, 2.0)[0], 0.012 + sx_point(r, r, th, 2.0)[1], z))
                      for th in [0.55 + (math.tau - 1.10) * k / 10 for k in range(11)]])
    faces, rv = G.bridge(bm, rings, CLOTH, lambda p: cloth_f(p, 31, 0.55), rnd, caps=(False, False), closed=False, jit=0.06)
    for idx, sgn in ((0, 1), (-1, -1)):
        vb, vt = rv[0][idx], rv[1][idx]
        f = bm.faces.new((vb, vt, bm.verts.new(vt.co + V((sgn * 0.024, -0.030, -0.044)))))
        G.paint(bm, [f], lambda p: cloth_f(p, 32, 0.55), rnd, CLOTH, 0.08)
    for (px, pz, pw, ph, tilt) in ((-0.07, 0.17, 0.075, 0.085, 0.10), (0.06, 0.27, 0.060, 0.070, -0.12)):             # заплатки на спине
        yb = chest_ab(pz, 0.0)[0] + 0.046
        G.box(bm, rnd, (px, yb, pz), (pw * 1.14, 0.004, ph * 1.14), lambda p: cloth_f(p, 22, 0.45), rot=(0, tilt, 0), mi=CLOTH)      # обшивка
        G.box(bm, rnd, (px, yb + 0.0025, pz), (pw, 0.004, ph), lambda p: cloth_f(p, 21, 1.35), rot=(0, tilt, 0), mi=CLOTH)           # заплата
    delete_faces(bm, lambda c: c.y > 0.07 and 0.20 < c.z < 0.25 and -0.12 < c.x < -0.03)                                # разрыв на спине
    for z0 in (0.12, 0.25):                                                                                         # пуговицы
        G.blob(bm, rnd, (0.058, front_y(z0, 0.058, 0.040) - 0.002, z0), (0.0085, 0.004, 0.0085), METAL, MISC, sub=1, jitter=0.0)
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


def mirror_x(bm):
    """Зеркало по X (для правой стороны): координаты и обход граней."""
    for v in bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))


def ragged(verts, rnd, amp):
    """Рваная кромка: вершины нижнего кольца сдвигаются по Z вразнобой."""
    for v in verts:
        v.co.z += rnd.uniform(-amp, amp * 0.4)


# ============================================================================ таз (шарнир — центр таза; шарниры бёдер — по бокам)
PELVIS = [(-0.13, 0.080, 0.112), (-0.06, 0.098, 0.146), (0.02, 0.094, 0.146), (0.09, 0.088, 0.134)]
HIP = (0.092, 0.0, -0.07)                       # шарнир бедра (левое)


def part_pelvis(rnd):
    bm = bmesh.new()
    shorts = lambda p: tuple(c * k for c, k in zip(cloth_f(p, 12, 0.95), (0.80, 0.78, 0.76)))
    seg = 14
    rings = []
    for z, a, b in PELVIS:
        rings.append([V((sx_point(a + 0.014, b + 0.014, k * math.tau / seg)[0], sx_point(a + 0.014, b + 0.014, k * math.tau / seg)[1], z))
                      for k in range(seg)])
    faces, rv = G.bridge(bm, rings, CLOTH, shorts, rnd, caps=(False, False), closed=True, jit=0.08)
    # ремень с пряжкой и свисающим концом
    belt = []
    for z in (0.062, 0.108):
        belt.append([V((sx_point(0.100 + 0.004, 0.142 + 0.004, k * math.tau / seg)[0], sx_point(0.104, 0.146, k * math.tau / seg)[1], z))
                     for k in range(seg)])
    G.bridge(bm, belt, MISC, LEATHER, rnd, caps=(False, False), closed=True, jit=0.05)
    G.box(bm, rnd, (0, -0.108, 0.085), (0.050, 0.012, 0.050), METAL, rot=(0, 0, 0))
    G.box(bm, rnd, (0, -0.1155, 0.085), (0.032, 0.006, 0.032), LEATHER)
    G.box(bm, rnd, (0.050, -0.106, 0.030), (0.014, 0.005, 0.120), LEATHER, rot=(0.05, 0, 0.12))                      # свисающий конец ремня
    for k in (-3, -2, 2, 3):                                                                                       # шлёвки
        th = k * 0.36
        x, y = sx_point(0.108, 0.150, th)
        G.box(bm, rnd, (x, y, 0.085), (0.014, 0.008, 0.050), LEATHER, rot=(0, 0, -th))
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


# ============================================================================ руки (шарнир — плечо / локоть / запястье; вниз по −Z)
UPPER_LEN, FORE_LEN = 0.285, 0.255
UPPER = [(z, a * 1.16, b * 1.16) for z, a, b in [(0.0, 0.046, 0.046), (-0.06, 0.037, 0.038), (-0.14, 0.031, 0.032), (-0.22, 0.030, 0.031), (-UPPER_LEN, 0.033, 0.034)]]
FORE = [(z, a * 1.16, b * 1.16) for z, a, b in [(0.0, 0.034, 0.036), (-0.06, 0.029, 0.033), (-0.14, 0.025, 0.028), (-0.21, 0.020, 0.025), (-FORE_LEN, 0.019, 0.024)]]


def part_upper_arm(rnd, side):
    """Плечо с рваным рукавом куртки; side=+1 — левое (+X), −1 — правое."""
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 20 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in UPPER], [(a, b) for z, a, b in UPPER], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0.002, -UPPER_LEN), (0.040, 0.040, 0.040), skin, SKIN, jitter=0.08)                              # локоть
    sl = [(0.070, 0.034, 0.034), (0.056, 0.058, 0.058), (0.022, 0.068, 0.067), (-0.04, 0.064, 0.063), (-0.10, 0.062, 0.061),
          (-0.175, 0.068, 0.066)]
    rings = []
    for z, a, b in sl:
        rings.append(G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 9, rnd=rnd, jit=0.03))
    sleeve = lambda p: cloth_f(p, 14 + side, 0.95)
    faces, rv = G.bridge(bm, rings, CLOTH, sleeve, rnd, caps=(True, False), closed=True, jit=0.08)
    ragged(rv[-1], rnd, 0.035)
    hem = [v.co.copy() for v in rv[-1]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0.0, -1), 0.03, 0.10, lambda p: cloth_f(p, 16, 0.85), per=1, center=V((0, 0, -0.175)))
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


def part_forearm(rnd, side):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 24 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in FORE], [(a, b) for z, a, b in FORE], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0.003, 0.0), (0.040, 0.040, 0.036), skin, SKIN, jitter=0.08)                                     # локоть
    G.blob(bm, rnd, (0, 0.032, -0.006), (0.020, 0.018, 0.024), LIGHT, SKIN, jitter=0.10)                                 # локтевой отросток
    G.tube(bm, rnd, [V((0, 0.027, -0.04)), V((0, 0.025, -0.14)), V((0, 0.022, -0.232))], [0.0065, 0.0060, 0.0055], 5, SKIN, LIGHT, caps=(True, True))
    for sx in (-1, 1):                                                                                                    # косточки запястья
        G.blob(bm, rnd, (sx * 0.019, 0.010, -0.244), (0.0105, 0.0105, 0.0105), LIGHT, SKIN, jitter=0.10)
    if side < 0:                                                                                                          # ремешок на правом запястье
        rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), 0.0235, 0.0290, 8, rnd=rnd) for z in (-0.195, -0.222)]
        G.bridge(bm, rings, MISC, LEATHER, rnd, caps=(False, False), closed=True)
        G.box(bm, rnd, (0.0, -0.025, -0.209), (0.030, 0.008, 0.030), METAL)
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


FINGERS = [(-0.026, (0.034, 0.023, 0.019), 0.20), (-0.009, (0.037, 0.025, 0.020), 0.30), (0.008, (0.034, 0.023, 0.018), 0.40),
           (0.024, (0.028, 0.019, 0.016), 0.50)]


def part_hand(rnd, side):
    """Кисть левая (ладонь смотрит на −X, большой палец вперёд −Y); правая — зеркало. Длинные скрюченные пальцы с ногтями-когтями."""
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 28)
    palm = [(0.0, 0.015, 0.026), (-0.02, 0.014, 0.034), (-0.055, 0.0125, 0.039), (-0.088, 0.0115, 0.040)]
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in palm], [(a, b) for z, a, b in palm], 8, SKIN, skin, up=(1, 0, 0), caps=(True, True), jit=0.04)
    for fy, lens, c0 in FINGERS:
        G.blob(bm, rnd, (0.011, fy, -0.088), (0.0100, 0.0100, 0.0110), skin, SKIN, jitter=0.08)                         # костяшка
        G.tube(bm, rnd, [V((0.012, fy * 0.5, -0.012)), V((0.012, fy, -0.088))], [0.0034, 0.0034], 4, SKIN, LIGHT, caps=(True, True))   # сухожилие
        p = V((0, fy, -0.090))
        pts, th, ang = [p.copy()], 0.0, [c0, c0 + 0.38, c0 + 0.78]
        for ln, th in zip(lens, ang):
            p = p + V((-math.sin(th), fy * 0.10, -math.cos(th))).normalized() * ln
            pts.append(p.copy())
        G.tube(bm, rnd, pts, [0.0088, 0.0078, 0.0066, 0.0052], 5, SKIN, skin, caps=(True, True), up=(1, 0, 0))
        for q in pts[1:3]:
            G.blob(bm, rnd, q, (0.0078, 0.0078, 0.0078), skin, SKIN, sub=1, jitter=0.06)
        d = (pts[-1] - pts[-2]).normalized()
        G.spike(bm, rnd, pts[-1] - d * 0.002, pts[-1] + d * 0.014, 0.0050, 0.0014, BONE_DK, seg=4)                       # коготь
    tp = [V((-0.012, -0.040, -0.026)), V((-0.026, -0.052, -0.058)), V((-0.034, -0.050, -0.088))]
    G.tube(bm, rnd, tp, [0.0115, 0.0092, 0.0070], 5, SKIN, skin, caps=(True, True), up=(1, 0, 0))
    G.spike(bm, rnd, tp[-1] - V((0, 0, 0.002)), tp[-1] + V((-0.004, 0.0, -0.014)), 0.0052, 0.0014, BONE_DK, seg=4)
    bmesh.ops.scale(bm, vec=(1.22, 1.22, 1.22), verts=bm.verts)
    if side < 0:
        mirror_x(bm)
    G.uv_pass(bm)
    return bm


# ============================================================================ ноги (шарнир — бедро / колено / лодыжка; вниз по −Z)
THIGH_LEN, SHIN_LEN, ANKLE_H = 0.41, 0.38, 0.09
THIGH = [(z, a * 1.10, b * 1.10) for z, a, b in [(0.0, 0.070, 0.072), (-0.10, 0.064, 0.066), (-0.22, 0.052, 0.055), (-0.32, 0.044, 0.046), (-THIGH_LEN, 0.040, 0.042)]]
SHIN = [(z, a * 1.12, b * 1.12) for z, a, b in [(0.0, 0.042, 0.044), (-0.06, 0.038, 0.040), (-0.16, 0.031, 0.032), (-0.27, 0.026, 0.028), (-SHIN_LEN, 0.028, 0.030)]]


def part_thigh(rnd, side):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 30 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in THIGH], [(a, b) for z, a, b in THIGH], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0, 0.0), (0.072, 0.072, 0.062), skin, SKIN, jitter=0.08)                                          # тазобедренный сустав
    G.blob(bm, rnd, (0, -0.030, -THIGH_LEN + 0.004), (0.031, 0.021, 0.035), LIGHT, SKIN, jitter=0.10)                       # коленная чашечка
    for sx in (-1, 1):
        G.blob(bm, rnd, (sx * 0.029, 0.004, -THIGH_LEN + 0.002), (0.020, 0.024, 0.026), skin, SKIN, jitter=0.08)           # мыщелки
    sh = [(0.045, 0.088, 0.090), (-0.05, 0.080, 0.082), (-0.15, 0.078, 0.080), (-0.225, 0.084, 0.086)]
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 10, rnd=rnd, jit=0.03) for z, a, b in sh]
    shorts = lambda p: tuple(c * k for c, k in zip(cloth_f(p, 34 + side, 0.95), (0.80, 0.78, 0.76)))
    faces, rv = G.bridge(bm, rings, CLOTH, shorts, rnd, caps=(False, False), closed=True, jit=0.08)
    ragged(rv[-1], rnd, 0.04)
    hem = [v.co.copy() for v in rv[-1]]
    hem.append(hem[0].copy())
    fringe(bm, rnd, hem, (0, 0, -1), 0.03, 0.09, lambda p: cloth_f(p, 36, 0.80), per=2, center=V((0, 0, -0.225)), flare=0.012)
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


def part_shin(rnd, side):
    bm = bmesh.new()
    skin = lambda p: skin_f(p, 40 + side)
    G.tube(bm, rnd, [V((0, 0, z)) for z, a, b in SHIN], [(a, b) for z, a, b in SHIN], 8, SKIN, skin, up=(0, -1, 0), caps=(True, True), jit=0.03)
    G.blob(bm, rnd, (0, 0, 0.0), (0.044, 0.044, 0.040), skin, SKIN, jitter=0.08)                                          # колено
    G.tube(bm, rnd, [V((0, -0.036, -0.06)), V((0, -0.030, -0.18)), V((0, -0.026, -0.29))], [0.0075, 0.0070, 0.0062], 5, SKIN, LIGHT, caps=(True, True))   # гребень голени
    G.blob(bm, rnd, (0, 0.020, -0.13), (0.030, 0.026, 0.060), skin, SKIN, jitter=0.10)                                    # икра
    # повязка на колене с пряжкой и свисающим концом
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), 0.054, 0.058, 9, rnd=rnd, jit=0.03) for z in (0.028, -0.062)]
    G.bridge(bm, rings, CLOTH, lambda p: cloth_f(p, 44 + side, 0.55), rnd, caps=(False, False), closed=True, jit=0.08)
    G.box(bm, rnd, (0.0, -0.056, -0.016), (0.026, 0.008, 0.036), METAL, rot=(0.1, 0, 0))
    G.box(bm, rnd, (0.030, -0.058, -0.075), (0.014, 0.004, 0.090), LEATHER, rot=(0.12, 0, -0.10))
    # голенище ботинка с отворотом и шнуровкой
    sh = [(-0.205, 0.066, 0.068), (-0.222, 0.059, 0.062), (-0.255, 0.055, 0.058), (-0.34, 0.051, 0.053), (-0.390, 0.053, 0.055)]
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), a, b, 10, rnd=rnd, jit=0.02) for z, a, b in sh]
    boot = lambda p: tuple(c * 0.90 for c in cloth_f(p, 48 + side, 0.82))
    faces, rv = G.bridge(bm, rings, CLOTH, boot, rnd, caps=(False, False), closed=True, jit=0.07)
    for z0, ang in ((-0.245, 0.4), (-0.285, -0.3), (-0.325, 0.35), (-0.360, -0.35)):
        a = 0.055 + 0.0 * z0
        G.box(bm, rnd, (0, -0.056, z0), (0.046, 0.005, 0.007), (0.20, 0.15, 0.09), rot=(0, ang, 0))
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == SKIN])
    G.uv_pass(bm)
    return bm


FOOT = [(0.084, 0.042, 0.016), (0.052, 0.052, 0.034), (0.0, 0.058, 0.046), (-0.060, 0.060, 0.020), (-0.120, 0.062, -0.005),
        (-0.170, 0.058, -0.022), (-0.200, 0.046, -0.034)]       # y, полуширина, верх (z)
SOLE = 0.024                                                     # толщина подошвы; низ ботинка на z = −ANKLE_H


def part_foot(rnd, side):
    """Ботинок ниже голенища: подошва, каблук, носок, шнуровка; шарнир — лодыжка, подошва на z = −ANKLE_H, носок вперёд (−Y)."""
    bm = bmesh.new()
    boot = lambda p: tuple(c * 0.90 for c in cloth_f(p, 52 + side, 0.82))
    zb = -ANKLE_H + SOLE
    pts = [V((0, y, (top + zb) / 2)) for y, w, top in FOOT]
    rad = [((top - zb) / 2, w) for y, w, top in FOOT]
    G.tube(bm, rnd, pts, rad, 10, CLOTH, boot, up=(0, 0, 1), caps=(True, True), n=3.0, jit=0.02)
    G.tube(bm, rnd, [V((0, y, -ANKLE_H + SOLE / 2)) for y, w, top in FOOT], [(SOLE / 2, w + 0.005) for y, w, top in FOOT], 8, MISC,
           LEATHER, up=(0, 0, 1), caps=(True, True), n=3.0)
    G.box(bm, rnd, (0, 0.062, -ANKLE_H + 0.010), (0.092, 0.046, 0.022), LEATHER)                                          # каблук
    rings = [G.ring(V((0, 0, z)), V((0, -1, 0)), V((1, 0, 0)), 0.066, 0.068, 10, rnd=rnd, jit=0.02) for z in (0.058, -0.014)]
    G.bridge(bm, rings, CLOTH, boot, rnd, caps=(False, False), closed=True, jit=0.06)                                    # манжета-стык с голенищем
    for y0 in (-0.020, -0.050, -0.080):                                                                                  # шнуровка по подъёму
        top = interp([(y, w, t) for y, w, t in FOOT][::-1], y0, 0)[2]
        G.box(bm, rnd, (0, y0, top + 0.002), (0.050, 0.008, 0.005), (0.20, 0.15, 0.09), rot=(0, 0, 0.35 if y0 > -0.04 else -0.35))
    G.facet(bm, rnd, [f for f in bm.faces if f.material_index == CLOTH])
    G.uv_pass(bm)
    return bm


# <<END>>
