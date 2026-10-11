"""Геометрические помощники для зомби: кольца и лофты, трубки по пути, блобы, вмятины, краска вершин, UV.

Все функции кладут геометрию в переданный bmesh. Грани красятся в цвет вершин «Color» (множится на текстуру материала
кожи/ткани, у «misc» — это и есть цвет) с лёгким разбросом яркости по граням — отсюда гранёный low-poly вид.
Слоты материалов: SKIN (текстура кожи), CLOTH (текстура ткани, двусторонняя), MISC (кости, зубы, металл — цвет вершин), EYE и EYE2 (свечение).
"""
import math

import bmesh
from mathutils import Matrix, Vector

import zone_lib as Z

SKIN, CLOTH, MISC, EYE, EYE2 = 0, 1, 2, 3, 4          # EYE2 — яркая сердцевина глаза
TILE = {SKIN: 0.30, CLOTH: 0.36}          # метров на один повтор текстуры (UV — по доминирующей оси нормали)
FRONT = Vector((0, -1, 0))                # «вперёд» у частей — −Y Blender (+Z в glTF)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def mix(a, b, k):
    k = clamp(k)
    return tuple(a[i] + (b[i] - a[i]) * k for i in range(3))


def noise(x, y, z, k=1.0):
    """Дешёвый детерминированный шум −1…1 для пятен на коже и ткани."""
    return math.sin(x * 31 + k) * math.sin(y * 27 + 2 * k) * math.sin(z * 23 + 3 * k)


def smooth(a, b, x):
    k = clamp((x - a) / (b - a))
    return k * k * (3 - 2 * k)


# ============================================================================ краска
def _lay(bm):
    return bm.loops.layers.float_color.get("Color") or bm.loops.layers.float_color.new("Color")


def paint(bm, faces, color, rnd=None, mi=None, jit=0.07):
    """Цвет вершин: color — rgb либо функция (x, y, z) → rgb; у каждой грани разброс яркости ±jit."""
    lay = _lay(bm)
    for f in faces:
        j = 1.0 + (rnd.uniform(-jit, jit) if rnd else 0.0)
        if mi is not None:
            f.material_index = mi
        for lp in f.loops:
            c = color(lp.vert.co) if callable(color) else color
            lp[lay] = (*[clamp(v * j, 0, 1.6) for v in c], 1.0)


def faces_of(verts):
    return list({f for v in verts for f in v.link_faces})


def uv_pass(bm):
    """Мировая (в системе части) проекция по оси нормали для граней с текстурой."""
    for mi, tile in TILE.items():
        fs = [f for f in bm.faces if f.material_index == mi]
        if fs:
            Z.box_uv(fs, bm, tile)


# ============================================================================ кольца и лофты
def ring(c, N, B, a, b, seg, phase=0.0, n=2.0, rnd=None, jit=0.0):
    """Эллиптическое (n=2) или «квадратное» (n>2) сечение с центром c в плоскости (N, B); a — по N, b — по B."""
    out = []
    for k in range(seg):
        t = phase + k * math.tau / seg
        ct, st = math.cos(t), math.sin(t)
        if n != 2.0:
            ct = math.copysign(abs(ct) ** (2.0 / n), ct)
            st = math.copysign(abs(st) ** (2.0 / n), st)
        r = 1.0 + (rnd.uniform(-jit, jit) if (rnd and jit) else 0.0)
        out.append(Vector(c) + N * (a * ct * r) + B * (b * st * r))
    return out


def bridge(bm, rings, mi, color, rnd=None, caps=(False, False), closed=True, jit=0.07):
    """Грани между соседними кольцами (равное число вершин); нормали — от центра своего кольца, крышки — наружу по ходу пути.
    Возвращает (грани, вершины колец)."""
    rv = [[bm.verts.new(p) for p in r] for r in rings]
    seg = len(rv[0])
    faces = []
    last = seg if closed else seg - 1
    for i in range(len(rv) - 1):
        for k in range(last):
            faces.append(bm.faces.new((rv[i][k], rv[i][(k + 1) % seg], rv[i + 1][(k + 1) % seg], rv[i + 1][k])))
    cen = [sum(r, Vector()) / len(r) for r in rings]
    for f in faces:
        f.normal_update()
        fc = f.calc_center_median()
        i = min(range(len(rv)), key=lambda j: (fc - cen[j]).length_squared)
        if f.normal.dot(fc - cen[i]) < 0:
            f.normal_flip()
    if len(rings) > 1:
        for on, ri, ref in ((caps[0], 0, cen[0] - cen[1]), (caps[1], -1, cen[-1] - cen[-2])):
            if on:
                f = bm.faces.new(rv[ri])
                f.normal_update()
                if f.normal.dot(ref) < 0:
                    f.normal_flip()
                faces.append(f)
    paint(bm, faces, color, rnd, mi, jit)
    return faces, rv


def frames(pts, up):
    """Системы координат вдоль пути: касательная T, нормаль N (проекция up), бинормаль B."""
    pts = [Vector(p) for p in pts]
    out = []
    upv = Vector(up).normalized()
    for i, p in enumerate(pts):
        T = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        N = upv - T * upv.dot(T)
        if N.length < 1e-4:
            N = Vector((1, 0, 0)) - T * T.x
        N.normalize()
        out.append((T, N, T.cross(N)))
    return out


def tube(bm, rnd, pts, radii, seg, mi, color, up=(0, 0, 1), caps=(True, True), n=2.0, phase=0.0, jit=0.0):
    """Трубка по пути pts; radii — число или (a, b) на точку (a вдоль N=проекция up, b вдоль B). Возвращает (грани, кольца вершин)."""
    fr = frames(pts, up)
    rings = []
    for (T, N, B), p, r in zip(fr, pts, radii if hasattr(radii, "__len__") else [radii] * len(pts)):
        a, b = (r, r) if not hasattr(r, "__len__") else r
        rings.append(ring(p, N, B, a, b, seg, phase, n, rnd, jit))
    return bridge(bm, rings, mi, color, rnd, caps, True)


# ============================================================================ примитивы
def blob(bm, rnd, c, size, color, mi=SKIN, sub=1, jitter=0.10, rot=(0, 0, 0)):
    mat = (Matrix.Translation(c) @ Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y")
           @ Matrix.Rotation(rot[0], 4, "X") @ Matrix.Diagonal((*size, 1.0)))
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0, matrix=mat)
    for v in res["verts"]:
        if jitter:
            v.co += Vector((rnd.uniform(-1, 1) * size[0], rnd.uniform(-1, 1) * size[1], rnd.uniform(-1, 1) * size[2])) * jitter
    fs = faces_of(res["verts"])
    paint(bm, fs, color, rnd, mi)
    return fs


def box(bm, rnd, c, size, color, rot=(0, 0, 0), mi=MISC, taper=None, jit=0.0):
    """Бокс с центром c; rot — углы вокруг X, Y, Z (рад); taper=(kx, ky) — сужение верхней грани (по +Z)."""
    mat = (Matrix.Translation(c) @ Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y")
           @ Matrix.Rotation(rot[0], 4, "X") @ Matrix.Diagonal((*size, 1.0)))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=mat)
    if taper:
        for v in res["verts"]:
            loc = mat.inverted() @ v.co
            if loc.z > 0:
                v.co = mat @ Vector((loc.x * taper[0], loc.y * taper[1], loc.z))
    if jit:
        for v in res["verts"]:
            v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * jit
    fs = faces_of(res["verts"])
    paint(bm, fs, color, rnd, mi)
    return fs


def spike(bm, rnd, a, b, r0, r1, color, seg=4, mi=MISC, caps=True):
    """Конус между точками a и b (когти, обломки, зубы, лохмотья)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    M = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    res = bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r0, radius2=r1, depth=d.length, matrix=M)
    fs = faces_of(res["verts"])
    paint(bm, fs, color, rnd, mi)
    return fs


# ============================================================================ деформации
def dent(verts, c, r, d, axis):
    """Гауссова вмятина (d<0 вдоль axis — выпуклость наружу, если axis смотрит наружу): вершины рядом с c сдвигаются на d·axis."""
    c, ax = Vector(c), Vector(axis).normalized()
    for v in verts:
        w = math.exp(-(((v.co - c).length) / r) ** 2)
        if w > 0.01:
            v.co += ax * (d * w)


def jitter_verts(verts, rnd, amp):
    for v in verts:
        v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * amp


def count_tris(bm):
    return sum(len(f.verts) - 2 for f in bm.faces)


def facet(bm, rnd, faces=None):
    """Четырёхугольники → треугольники со случайной диагональю: «кристаллический» low-poly вид вместо сетки колец."""
    quads = [f for f in (faces or bm.faces) if f.is_valid and len(f.verts) == 4]
    a = [f for f in quads if rnd.random() < 0.5]
    b = [f for f in quads if f not in set(a)]
    if a:
        bmesh.ops.triangulate(bm, faces=a, quad_method="FIXED")
    if b:
        bmesh.ops.triangulate(bm, faces=b, quad_method="ALTERNATE")


# ============================================================================ цвета и общие приёмы
# ---- цвета вершин (линейные). Для SKIN/CLOTH множатся на текстуру, для MISC — итоговый цвет.
BONE = (0.56, 0.52, 0.40)          # кость, зубы (слоновая кость)
BONE_DK = (0.27, 0.23, 0.15)       # старая кость, ногти
DARK = (0.012, 0.010, 0.010)       # провалы: глазницы, ноздри, рот
MOUTH = (0.050, 0.014, 0.014)      # нёбо, язык
GUM = (0.10, 0.040, 0.036)         # дёсны
METAL = (0.30, 0.29, 0.27)         # пряжка, заклёпки (потёртое серебро)
DARK_BLUE = (0.030, 0.040, 0.055)  # стенки глазниц — тёмная сине-серая полость
LEATHER = (0.060, 0.040, 0.030)    # ремень, браслеты, подошвы
TINT_GREY = (0.80, 0.80, 0.83)     # множители к ткани: перед жилета, рубашка — серо-коричневый
TINT_RED = (0.95, 0.70, 0.66)      # шорты и спина жилета — красновато-бурый
EYE_COL = (0.34, 0.37, 0.34)


def skin_f(p, k=1.0):
    """Множитель к текстуре кожи: мягкие пятна светлее/темнее."""
    x, y, z = p
    n = noise(x * 1.1, y * 1.1, z * 1.3, k)
    f = 0.90 + 0.12 * n
    m = noise(x * 2.3, y * 1.9, z * 2.1, k + 7)
    if m > 0.55:                                            # синюшные пятна
        return (f * 0.90, f * 0.86, f * 0.95)
    return (f, f * 0.99, f * 0.96)


def cloth_f(p, k=1.0, base=1.0):
    x, y, z = p
    n = noise(x * 1.7, y * 1.5, z * 1.9, k)
    f = base * (0.92 + 0.14 * n)
    s = noise(x * 2.6, y * 2.2, z * 2.8, k + 4)
    if s > 0.6:                                             # бурые пятна
        return (f * 0.78, f * 0.66, f * 0.58)
    return (f, f, f)


def lerp(a, b, k):
    return a + (b - a) * k


def interp(table, z, i0=0):
    """Линейная интерполяция по таблице строк (z, v1, v2, …) → кортеж значений на высоте z."""
    for a, b in zip(table, table[1:]):
        if (z - a[i0]) * (z - b[i0]) <= 0:
            k = (z - a[i0]) / (b[i0] - a[i0]) if b[i0] != a[i0] else 0.0
            return tuple(lerp(a[i], b[i], k) for i in range(len(a)))
    return table[0] if z < table[0][i0] else table[-1]


def sx_point(a, b, th, n=2.4):
    """Точка на «квадратном» эллипсе: th = 0 — перёд (−Y), положительные th — сторона +X. Возвращает (x, y)."""
    s, c = math.sin(th), math.cos(th)
    s = math.copysign(abs(s) ** (2.0 / n), s)
    c = math.copysign(abs(c) ** (2.0 / n), c)
    return b * s, -a * c


def fringe(bm, rnd, pts, down, lmin, lmax, color, mi=CLOTH, per=1, flare=0.010, center=None, wob=0.4):
    """Лохмотья вдоль кромки: из каждой пары соседних точек pts — треугольные лоскуты разной длины, расходящиеся наружу."""
    down = Vector(down).normalized()
    out = []
    for i in range(len(pts) - 1):
        p, q = Vector(pts[i]), Vector(pts[i + 1])
        for j in range(per):
            a, b = p.lerp(q, j / per), p.lerp(q, (j + 1) / per)
            m = a.lerp(b, rnd.uniform(0.3, 0.7))
            side = (b - a).normalized() * rnd.uniform(-wob, wob) * (b - a).length
            outv = ((m - Vector(center)).normalized() * flare) if center is not None else Vector()
            tip = m + down * rnd.uniform(lmin, lmax) + side + outv
            out.append(bm.faces.new((bm.verts.new(a), bm.verts.new(b), bm.verts.new(tip))))
    paint(bm, out, color, rnd, mi, 0.10)
    return out


def delete_faces(bm, pred, mi=CLOTH):
    """Удаляет грани материала mi (по умолчанию ткань), центр которых удовлетворяет pred(центр) — дыры в одежде не трогают тело."""
    fs = [f for f in bm.faces if f.material_index == mi and pred(f.calc_center_median())]
    if fs:
        bmesh.ops.delete(bm, geom=fs, context="FACES")
    return len(fs)
