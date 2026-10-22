"""Пистолет и лопата: low-poly, острые грани, PBR-тайлы зоны (tile_metal / tile_wood) × цвет вершин (воронение, ржавчина, земля).

pistol_old_a  — старый самозарядный пистолет (силуэт классического 1911), ≈ 21.5 × 13.5 см;
shovel_grave_a — штыковая лопата могильщика с D-образной рукоятью, ≈ 1.10 м.

Каждая модель — один объект, имя = objectId (соглашение в src/data/objects.catalog.ts), origin — нижняя точка/основание
(пистолет — центр низа рукояти, лопата — остриё полотна), «перед» модели (ствол пистолета, лицевая сторона полотна)
смотрит на −Y Blender = +Z glTF, вверх = +Z. Металл и дерево — два материала на модель (пистолет: tile_gunmetal, лопата: ржавый tile_metal); в сцене модели
выложены рядом только для просмотра, в .glb origin всегда (0, 0, 0).

Сцена: assets_src/blender/props_tools.blend (создаётся из night_keeper_base.blend — new_file()). Из окна Blender (через MCP):

    import sys, importlib; sys.path.insert(0, r"D:\\dev\\denisovLoh\\assets_src\\blender")
    import props_tools as T; importlib.reload(T); T.build_all(); T.export_all()
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

import zone_lib as Z

BASE_BLEND = os.path.join(Z.HERE, "night_keeper_base.blend")
TOOLS_BLEND = os.path.join(Z.HERE, "props_tools.blend")
OUT_DIR = os.path.join(Z.REPO, "public", "models", "props")
DISPLAY = {"pistol_old_a": (-0.35, 0.0, 0.0), "shovel_grave_a": (0.25, 0.0, 0.0)}
STEEL, WOOD = 0, 1          # индексы материалов модели


# ============================================================================ служебное
def new_file():
    """Пустая сцена из базового файла (единицы, свет, ref-фигура 1.7 м) → props_tools.blend."""
    bpy.ops.wm.open_mainfile(filepath=BASE_BLEND)
    bpy.ops.wm.save_as_mainfile(filepath=TOOLS_BLEND, compress=False, relative_remap=True)
    return {"file": TOOLS_BLEND, "objects": [o.name for o in bpy.data.objects]}


def materials(metal):
    """[металл, дерево]: тайлы зоны × цвет вершин (атрибут «Color»). Металл — tile_gunmetal (пистолет) или tile_metal
    (лопата, ржавчина); дерево — tile_wood. Уже созданные материалы переиспользуются (zone_lib.tile_material пересоздаёт
    материал с тем же именем и оставил бы пустые слоты у готовой модели)."""
    spec = ((f"mat_tool_{metal}", {"gunmetal": "tile_gunmetal", "iron": "tile_metal"}[metal]), ("mat_tool_wood", "tile_wood"))
    return [bpy.data.materials.get(n) or Z.tile_material(n, tile, vcolor=True) for n, tile in spec]


def prism(bm, pts, x0, x1, mi=STEEL, tile=0.25, rgb=None):
    """Контур pts = (L, z) в плоскости «вперёд—вверх», выдавленный по X от x0 до x1 (L вперёд → −Y). Возвращает грани."""
    a = [bm.verts.new((x0, -L, z)) for L, z in pts]
    b = [bm.verts.new((x1, -L, z)) for L, z in pts]
    n = len(pts)
    faces = [bm.faces.new(a), bm.faces.new(b[::-1])]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    for f in faces:
        f.material_index = mi
    Z.box_uv(faces, bm, tile)
    if rgb:
        Z.paint(bm, faces, rgb)
    return faces


def box(bm, c, s, mi=STEEL, tile=0.25, rgb=None, M=None):
    """Бокс: центр c = (x, L, z) в осях модели (L вперёд), размеры s = (по x, по L, по z)."""
    cx, L, cz = c
    faces = Z.add_box(bm, (cx, -L, cz), (s[0], s[1], s[2]), M, tile, mi=mi)
    if rgb:
        Z.paint(bm, faces, rgb)
    return faces


def cyl(bm, c, r1, r2, depth, axis="L", seg=8, mi=STEEL, tile=0.25, rgb=None, rz=0.0):
    """Цилиндр/конус; ось вдоль L (вперёд), X или Z. c = (x, L, z)."""
    cx, L, cz = c
    M = {"Z": Matrix.Identity(4), "L": Matrix.Rotation(math.pi / 2, 4, "X"), "X": Matrix.Rotation(math.pi / 2, 4, "Y")}[axis]
    faces = Z.add_cone(bm, (0, 0, 0), r1, r2, depth, seg=seg, M=Matrix.Translation((cx, -L, cz)) @ M, mi=mi, tile=tile, rz=rz)
    if rgb:
        Z.paint(bm, faces, rgb)
    return faces


def wear(bm, faces, rnd, base, amount=0.12):
    """Раскрашивает грани цветом base с лёгким разбросом — «живой» металл/дерево вместо плоского тона."""
    for f in faces:
        k = 1.0 + rnd.uniform(-amount, amount)
        Z.paint(bm, [f], (base[0] * k, base[1] * k, base[2] * k))


def ensure_colors(bm):
    """Грань без цвета вершин дала бы чёрный (albedo × 0): докрашиваем сталью/деревом по материалу."""
    lay = bm.loops.layers.float_color.get("Color") or bm.loops.layers.float_color.new("Color")
    for f in bm.faces:
        if all(lp[lay][3] == 0 for lp in f.loops):
            Z.paint(bm, [f], BLUED if f.material_index == STEEL else GRIP_WOOD)


def finish(name, bm, metal, flat=True):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    ensure_colors(bm)
    o, tris = Z.finish(name, bm, materials(metal), smooth=not flat)
    return o, tris


# ============================================================================ пистолет
BLUED = (1.0, 1.0, 1.0)           # воронёная сталь: тон даёт сам tile_gunmetal, цвет вершин — лишь разброс между гранями
BLUED_LIGHT = (1.5, 1.5, 1.55)    # потёртые рёбра и мелкие детали (курок, мушка, предохранитель) — светлее
BLACK = (0.04, 0.04, 0.045)
GRIP_WOOD = (1.6, 1.2, 0.95)


def build_pistol():
    """Старый самозарядный пистолет. L = 0 — тыльная плоскость рукояти, L = 0.216 — дульный срез; z = 0 — низ рукояти."""
    Z.clear("pistol_old_a")
    rnd = random.Random(1911)
    bm = bmesh.new()
    FX = 0.0135           # полутолщина рамы
    SW = 0.0145           # полутолщина затвора

    def steel(faces, base=BLUED, k=0.10):
        wear(bm, faces, rnd, base, k)

    # --- рама: рукоять с наклоном ≈ 17° и ствольная коробка под затвором
    steel(prism(bm, [(0.000, 0.000), (0.047, 0.000), (0.074, 0.086), (0.027, 0.086)], -FX, FX))
    steel(prism(bm, [(0.026, 0.080), (0.074, 0.080), (0.192, 0.080), (0.192, 0.095), (0.026, 0.095)], -FX, FX))
    # --- спусковая скоба и спуск
    steel(prism(bm, [(0.074, 0.082), (0.082, 0.082), (0.0835, 0.054), (0.078, 0.050)], -0.0045, 0.0045))
    steel(prism(bm, [(0.078, 0.054), (0.118, 0.054), (0.118, 0.048), (0.080, 0.046)], -0.0045, 0.0045))
    steel(prism(bm, [(0.110, 0.080), (0.118, 0.082), (0.122, 0.048), (0.114, 0.048)], -0.0045, 0.0045))
    steel(prism(bm, [(0.090, 0.082), (0.098, 0.082), (0.094, 0.056), (0.088, 0.060)], -0.0030, 0.0030), BLUED_LIGHT, 0.06)
    # --- затвор: фаски по краям, мушка и целик
    steel(prism(bm, [(0.020, 0.095), (0.207, 0.095), (0.207, 0.124), (0.198, 0.129), (0.030, 0.129), (0.020, 0.124)], -SW, SW))
    steel(prism(bm, [(0.190, 0.129), (0.200, 0.129), (0.197, 0.137), (0.191, 0.137)], -0.0026, 0.0026), BLUED_LIGHT, 0.05)
    steel(prism(bm, [(0.024, 0.129), (0.037, 0.129), (0.035, 0.136), (0.026, 0.136)], -0.0068, -0.0016), BLUED_LIGHT, 0.05)
    steel(prism(bm, [(0.024, 0.129), (0.037, 0.129), (0.035, 0.136), (0.026, 0.136)], 0.0016, 0.0068), BLUED_LIGHT, 0.05)
    # --- насечки на затворе (тёмные полоски) и окно выброса гильз справа (−X)
    for i in range(7):
        L = 0.024 + i * 0.0052
        for sx in (-1, 1):
            box(bm, (sx * (SW + 0.0002), L, 0.1105), (0.0007, 0.0021, 0.027), rgb=BLACK)
    box(bm, (-(SW + 0.0002), 0.112, 0.1115), (0.0007, 0.036, 0.0165), rgb=BLACK)
    # --- ствол и втулка: втулка выступает из затвора, из неё виден ствол с тёмным каналом
    steel(cyl(bm, (0, 0.2085, 0.1095), 0.0098, 0.0098, 0.0155, "L", 10), BLUED_LIGHT, 0.05)
    steel(cyl(bm, (0, 0.2175, 0.1095), 0.0060, 0.0060, 0.0090, "L", 8), BLUED_LIGHT, 0.04)
    cyl(bm, (0, 0.2222, 0.1095), 0.0036, 0.0036, 0.0006, "L", 8, rgb=BLACK)
    # --- курок, предохранитель большого пальца (слева, +X), задержка затвора, безопасность рукояти
    steel(prism(bm, [(0.026, 0.100), (0.014, 0.103), (0.008, 0.115), (0.016, 0.123), (0.026, 0.121)], -0.0042, 0.0042), BLUED_LIGHT, 0.05)
    steel(prism(bm, [(0.046, 0.098), (0.068, 0.098), (0.065, 0.1045), (0.049, 0.1045)], SW, SW + 0.0045), BLUED_LIGHT, 0.05)
    steel(prism(bm, [(0.081, 0.091), (0.092, 0.091), (0.092, 0.095), (0.081, 0.095)], SW - 0.001, SW + 0.0030), BLUED_LIGHT, 0.05)
    steel(prism(bm, [(0.025, 0.066), (0.020, 0.090), (0.015, 0.102), (0.030, 0.102), (0.036, 0.080)], -0.0105, 0.0105))
    # --- основание магазина
    steel(prism(bm, [(-0.003, -0.007), (0.051, -0.007), (0.051, 0.000), (-0.003, 0.000)], -0.0145, 0.0145), BLUED_LIGHT, 0.06)
    # --- накладки рукояти: дерево, винты, ромбики насечки
    grip = [(0.004, 0.004), (0.043, 0.004), (0.0655, 0.079), (0.0305, 0.083)]
    for s in (-1, 1):
        x0, x1 = (FX, FX + 0.0045) if s > 0 else (-FX - 0.0045, -FX)
        wear(bm, prism(bm, grip, x0, x1, mi=WOOD, tile=0.2), rnd, GRIP_WOOD, 0.10)
        xo = s * (FX + 0.0045)
        cyl(bm, (xo + s * 0.0004, 0.0355, 0.060), 0.0036, 0.0036, 0.0010, "X", 8, rgb=BLUED_LIGHT)
        for zi in range(6):
            z = 0.014 + zi * 0.0105
            Lc = 0.0215 + (z / 0.086) * 0.027                  # середина рукояти на высоте z (наклон)
            for k in (-1, 0, 1):
                if zi in (4, 5) and k == 0 and abs(z - 0.060) < 0.006:
                    continue
                Lk = Lc + k * 0.0115
                r_a, r_b = (0.0034, 0.0004) if s > 0 else (0.0004, 0.0034)           # остриё ромбика — наружу
                f = cyl(bm, (xo + s * 0.0007, Lk, z), r_a, r_b, 0.0016, "X", 4, mi=WOOD, tile=0.2, rz=math.pi / 4)
                wear(bm, f, rnd, (1.3, 0.95, 0.75), 0.10)
    return finish("pistol_old_a", bm, "gunmetal")


# ============================================================================ лопата
# множители к ржавому tile_metal (тёмное кованое железо с оранжевыми пятнами ржавчины): поднимают яркость и тон
RUST = [(2.0, 1.6, 1.3), (1.7, 1.4, 1.2), (2.4, 1.9, 1.5)]
STEEL_TIP = (2.8, 2.7, 2.6)                    # зашлифованное землёй остриё
DIRT = (3.2, 2.3, 1.5)                          # налипшая земля
ASH = (2.0, 1.8, 1.5)


def blade_width(z):
    """Полуширина полотна на высоте z от острия: закруглённое остриё, плечи на 0.20 м, ровный верх."""
    pts = [(0.0, 0.006), (0.03, 0.040), (0.07, 0.078), (0.12, 0.105), (0.18, 0.116), (0.24, 0.118), (0.285, 0.115)]
    for (z0, w0), (z1, w1) in zip(pts, pts[1:]):
        if z <= z1:
            return w0 + (w1 - w0) * (z - z0) / (z1 - z0)
    return pts[-1][1]


def build_shovel():
    """Штыковая лопата. origin — остриё полотна; полотно в плоскости XZ, лицевая сторона к −Y, шток уходит вверх (+Z)."""
    Z.clear("shovel_grave_a")
    rnd = random.Random(1895)
    bm = bmesh.new()
    NZ, NX, TOP, T = 10, 9, 0.285, 0.0036
    SH_Y = 0.021                                       # ось штока позади полотна (+Y)

    # --- полотно: чуть вогнутое, толщина T; сетка по высоте и ширине, лицо и тыл + торцы
    def yc(x, z):
        return -0.011 * (x / 0.118) ** 2 + 0.010 * (z / TOP) ** 2          # поперечный изгиб (края вперёд) и лёгкий отгиб кверху

    F, B = [], []
    for j in range(NZ + 1):
        z = TOP * (j / NZ) ** 0.9
        w = blade_width(z)
        row_f, row_b = [], []
        for i in range(NX):
            x = -w + 2 * w * i / (NX - 1)
            row_f.append(bm.verts.new((x, yc(x, z) - T / 2, z)))
            row_b.append(bm.verts.new((x, yc(x, z) + T / 2, z)))
        F.append(row_f)
        B.append(row_b)
    blade = []
    for j in range(NZ):
        for i in range(NX - 1):
            blade.append(bm.faces.new((F[j][i], F[j][i + 1], F[j + 1][i + 1], F[j + 1][i])))
            blade.append(bm.faces.new((B[j][i], B[j + 1][i], B[j + 1][i + 1], B[j][i + 1])))
    for j in range(NZ):
        blade.append(bm.faces.new((F[j][0], F[j + 1][0], B[j + 1][0], B[j][0])))
        blade.append(bm.faces.new((F[j][NX - 1], B[j][NX - 1], B[j + 1][NX - 1], F[j + 1][NX - 1])))
    for i in range(NX - 1):
        blade.append(bm.faces.new((F[0][i], B[0][i], B[0][i + 1], F[0][i + 1])))
        blade.append(bm.faces.new((F[NZ][i], F[NZ][i + 1], B[NZ][i + 1], B[NZ][i])))
    bmesh.ops.recalc_face_normals(bm, faces=blade)
    for f in blade:
        f.material_index = STEEL
    Z.box_uv(blade, bm, 0.30)
    for f in blade:                                      # ржавчина пятнами; у острия — светлее (затёрто о землю), выше — земля
        c = f.calc_center_median()
        base = rnd.choice(RUST)
        k = 1.0 + rnd.uniform(-0.12, 0.12)
        t = min(max((c.z - 0.0) / 0.12, 0.0), 1.0)
        col = [b * k for b in base]
        if c.z < 0.06:
            col = [v * k2 for v, k2 in zip(STEEL_TIP, (rnd.uniform(0.9, 1.1),) * 3)]   # зашлифованное остриё
        elif 0.07 < c.z < 0.17 and rnd.random() < 0.40:
            col = [d * rnd.uniform(0.8, 1.15) for d in DIRT]  # налипшая земля
        Z.paint(bm, [f], tuple(col))

    # --- упоры для ноги (отогнутая назад кромка на плечах) и ребро жёсткости на тыльной стороне полотна
    for sx in (-1, 1):
        f = Z.add_box(bm, (sx * 0.080, 0.020, TOP - 0.002), (0.060, 0.016, 0.0075), None, 0.3, mi=STEEL)
        wear(bm, f, rnd, (2.0, 1.6, 1.3), 0.12)
    spine = [(0.000, 0.110), (0.012, 0.165), (0.017, 0.255), (0.017, 0.300), (0.000, 0.300)]      # профиль (y, z), y — назад
    f = prism(bm, [(-y, z) for y, z in spine], -0.011, 0.011, STEEL, 0.3)
    wear(bm, f, rnd, (1.9, 1.5, 1.25), 0.12)

    # --- втулка (гнездо) штока, заклёпки, обжимное кольцо
    f = cyl(bm, (0, -SH_Y, 0.352), 0.032, 0.0215, 0.150, "Z", 8, tile=0.3)
    wear(bm, f, rnd, (1.9, 1.5, 1.25), 0.12)
    for zr in (0.318, 0.372):
        for sx in (-1, 1):
            cyl(bm, (sx * 0.0225, -SH_Y, zr), 0.0042, 0.0034, 0.0075, "X", 6, tile=0.3, rgb=(2.0, 1.5, 1.2))
    f = cyl(bm, (0, -SH_Y, 0.425), 0.0245, 0.0245, 0.014, "Z", 8, tile=0.3)
    wear(bm, f, rnd, (1.6, 1.3, 1.1), 0.10)

    # --- деревянный шток (ясень): граненый, с лёгким сужением, и D-образная рукоять
    shaft = cyl(bm, (0, -SH_Y, 0.715), 0.0185, 0.0158, 0.575, "Z", 8, mi=WOOD, tile=0.25)
    wear(bm, shaft, rnd, ASH, 0.08)

    def seg(p0, p1, w, d, rgb):
        """Деревянный брусок между двумя точками в плоскости XZ (толщина w в плоскости, d по Y); концы перекрываются."""
        p0, p1 = Vector((p0[0], 0, p0[1])), Vector((p1[0], 0, p1[1]))
        mid = (p0 + p1) / 2
        ln = (p1 - p0).length + w * 0.9
        ang = math.atan2(p1.x - p0.x, p1.z - p0.z)
        M = Matrix.Translation((mid.x, SH_Y, mid.z)) @ Matrix.Rotation(ang, 4, "Y")
        f = Z.add_box(bm, (0, 0, 0), (w, d, ln), M, 0.25, mi=WOOD)
        wear(bm, f, rnd, rgb, 0.08)

    path = [(-0.056, 0.985), (-0.056, 1.052), (-0.038, 1.088), (0.038, 1.088), (0.056, 1.052), (0.056, 0.985)]
    for a, b in zip(path, path[1:]):
        seg((a[0], a[1]), (b[0], b[1]), 0.024, 0.032, ASH)
    f = Z.add_box(bm, (0, SH_Y, 0.9925), (0.136, 0.034, 0.015), None, 0.25, mi=WOOD)   # башмак рукояти на штоке
    wear(bm, f, rnd, ASH, 0.08)
    f = cyl(bm, (0, -SH_Y, 0.965), 0.0225, 0.0205, 0.030, "Z", 8, tile=0.3)           # стальной хомут на штоке
    wear(bm, f, rnd, (1.7, 1.7, 1.8), 0.10)
    return finish("shovel_grave_a", bm, "iron")


# ============================================================================ сборка и экспорт
STEPS = [build_pistol, build_shovel]


def place(obj):
    obj.location = DISPLAY[obj.name]
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def build_all():
    out = {}
    for fn in STEPS:
        o, tris = fn()
        place(o)
        out[o.name] = tris
    return out


def export(name):
    """Один объект → public/models/props/<name>.glb; на время экспорта модель в начале координат."""
    o = bpy.data.objects[name]
    loc = o.location.copy()
    o.location = (0, 0, 0)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    s = Z.export_settings()
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    if "export_vertex_color" in props.keys():
        s["export_vertex_color"] = "MATERIAL"
    s["use_selection"] = True
    path = os.path.join(OUT_DIR, name + ".glb")
    try:
        bpy.ops.export_scene.gltf(filepath=path, **s)
    finally:
        o.location = loc
    return os.path.getsize(path) // 1024


def export_all():
    return {name: export(name) for name in DISPLAY}
