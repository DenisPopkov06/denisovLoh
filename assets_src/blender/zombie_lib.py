"""Зомби (враждебный моб) «zombie_walker_a» по арт-листу: сутулый, жилистый, череп-лицо с оскалом и светящимися глазами,
рваная куртка-жилет, обрезанные шорты, повязки на коленях, тяжёлые ботинки. Рост ≈ 1.65 м, origin — на земле между ступнями,
лицом к −Y Blender (+Z glTF).

Модель — иерархия жёстких частей с шарнирами (пока без анимации): таз → туловище → голова → челюсть; туловище → плечо → предплечье →
кисть; таз → бедро → голень → ступня. Геометрия частей — zombie_head.py / zombie_body.py, общие приёмы — zombie_geo.py,
текстуры и материалы — zombie_textures.py (кожа и ткань — бесшовные PBR 512², локальные детали — цвет вершин).

Вызывается из окна Blender по шагам (прогресс виден вживую):
    import sys, importlib; sys.path.insert(0, r"D:\\dev\\denisovLoh\\assets_src\\blender")
    import zombie_lib as ZL; importlib.reload(ZL); ZL.build_zombie(); ZL.export()
"""
import importlib
import math
import random

import bpy
from mathutils import Euler, Matrix, Vector

import zone_lib as Z
import zombie_geo as G
importlib.reload(G)
import zombie_head as H
import zombie_body as B
import zombie_textures as ZT

NAME = "zombie_walker_a"
DISPLAY_POS = (-4.5, -27.0, 0.0)          # место в сцене props_kit.blend (в .glb не попадает)

MAKERS = {"pelvis": B.part_pelvis, "chest": B.part_chest, "head": H.part_head, "jaw": H.part_jaw,
          "upper_l": lambda r: B.part_upper_arm(r, 1), "upper_r": lambda r: B.part_upper_arm(r, -1),
          "fore_l": lambda r: B.part_forearm(r, 1), "fore_r": lambda r: B.part_forearm(r, -1),
          "hand_l": lambda r: B.part_hand(r, 1), "hand_r": lambda r: B.part_hand(r, -1),
          "thigh_l": lambda r: B.part_thigh(r, 1), "thigh_r": lambda r: B.part_thigh(r, -1),
          "shin_l": lambda r: B.part_shin(r, 1), "shin_r": lambda r: B.part_shin(r, -1),
          "foot_l": lambda r: B.part_foot(r, 1), "foot_r": lambda r: B.part_foot(r, -1)}
# часть: (родитель, смещение шарнира в системе родителя)
JOINTS = {"pelvis": (NAME, (0, 0, 0)), "chest": ("pelvis", (0, 0, 0.10)), "head": ("chest", (0, 0, B.NECK_Z)),
          "jaw": ("head", H.JAW_PIVOT),
          "upper_l": ("chest", B.SHOULDER), "upper_r": ("chest", (-B.SHOULDER[0], B.SHOULDER[1], B.SHOULDER[2])),
          "fore_l": ("upper_l", (0, 0, -B.UPPER_LEN)), "fore_r": ("upper_r", (0, 0, -B.UPPER_LEN)),
          "hand_l": ("fore_l", (0, 0, -B.FORE_LEN)), "hand_r": ("fore_r", (0, 0, -B.FORE_LEN)),
          "thigh_l": ("pelvis", B.HIP), "thigh_r": ("pelvis", (-B.HIP[0], B.HIP[1], B.HIP[2])),
          "shin_l": ("thigh_l", (0, 0, -B.THIGH_LEN)), "shin_r": ("thigh_r", (0, 0, -B.THIGH_LEN)),
          "foot_l": ("shin_l", (0, 0, -B.SHIN_LEN)), "foot_r": ("shin_r", (0, 0, -B.SHIN_LEN))}

# поза (градусы; вперёд для «вверх-торчащих» частей — +X, для свисающих — −X; ноги — через IK)
POSE = dict(pelvis_pos=(0.0, -0.03, 0.950), pelvis=(8, 0, 3), chest=(30, 0, -5), head=(-22, 4, 8), jaw=(0, 0, 0),
            upper_l=(-26, -22, 0), upper_r=(-30, 20, 0), fore_l=(-50, 0, 0), fore_r=(-44, 0, 0), hand_l=(-14, 0, 0), hand_r=(-20, 0, 0),
            foot_l=(0.285, -0.12, 18), foot_r=(-0.260, 0.07, -20))


def part(key):
    return bpy.data.objects[f"{NAME}_{key}"]


def build_zombie(M=None, pose=True, seed=66, ao=True, fix=True):
    """Создаёт (заново) пустышку-корень и 16 частей с шарнирами; возвращает число треугольников."""
    for m in (ZT,):
        importlib.reload(m)
    for o in list(bpy.data.objects):
        if o.name == NAME or o.name.startswith(NAME + "_"):
            bpy.data.objects.remove(o, do_unlink=True)
    for me in list(bpy.data.meshes):
        if me.name.startswith(NAME + "_") and me.users == 0:
            bpy.data.meshes.remove(me)
    mats = [bpy.data.materials.get(n) for n in ("mat_zombie_skin", "mat_zombie_cloth", "mat_zombie_misc", "mat_zombie_eyes", "mat_zombie_eyes_core")]
    if not all(mats):
        ZT.make_textures()
        mats = ZT.make_materials()
    rnd = random.Random(seed)
    root = bpy.data.objects.new(NAME, None)
    root.empty_display_type = "ARROWS"
    root.empty_display_size = 0.3
    root.location = DISPLAY_POS
    Z.collection().objects.link(root)
    objs, tris = {NAME: root}, 0
    for key, mk in MAKERS.items():
        o, t = Z.finish(f"{NAME}_{key}", mk(rnd), mats)
        tris += t
        parent, off = JOINTS[key]
        o.parent = objs[parent]
        o.location = off
        o.rotation_mode = "XYZ"
        objs[key] = o
    bpy.context.view_layer.update()
    if pose:
        apply_pose()
        if fix:
            audit_floating(snap=True)                                # подтянуть/вдавить всё, что не врастает в остальное тело
        if ao:
            bake_ao()
    return {"tris": tris, "parts": len(MAKERS)}


# ============================================================================ поза
def _rot(deg):
    return Euler([math.radians(a) for a in deg], "XYZ").to_matrix()


def _solve_leg(hip, ankle, side):
    """Два звена бедро/голень: колено — вперёд (−Y) и чуть наружу. Возвращает (R_бедра, R_голени) в мировых координатах."""
    d = ankle - hip
    L1, L2 = B.THIGH_LEN, B.SHIN_LEN
    D = min(d.length, L1 + L2 - 1e-4)
    dh = d.normalized()
    cos_a = (L1 * L1 + D * D - L2 * L2) / (2 * L1 * D)                       # угол у бедра между d и бедром
    a = math.acos(max(-1.0, min(1.0, cos_a)))
    pole = Vector((side * 0.25, -1.0, 0.0))
    pole = (pole - dh * pole.dot(dh)).normalized()
    t1 = dh * math.cos(a) + pole * math.sin(a)                                # направление бедро → колено
    knee = hip + t1 * L1
    s = (ankle - knee).normalized()

    def basis(down):
        z = -down
        y = Vector((-side * 0.15, 1.0, 0.0))
        y = (y - z * y.dot(z)).normalized()
        return Matrix((y.cross(z), y, z)).transposed()                       # столбцы x, y, z: локальный −Z смотрит вдоль звена

    return basis(t1), basis(s)


def apply_pose(P=None):
    """Ставит позу: туловище/руки — по углам, ноги — IK на заданные положения ступней, подошвы на z = 0."""
    P = P or POSE
    root = Vector(DISPLAY_POS)
    pl = part("pelvis")
    pl.location = P["pelvis_pos"]
    pl.rotation_euler = [math.radians(a) for a in P["pelvis"]]
    for k in ("chest", "head", "jaw", "upper_l", "upper_r", "fore_l", "fore_r", "hand_l", "hand_r"):
        part(k).rotation_euler = [math.radians(a) for a in P[k]]
    Rp = _rot(P["pelvis"])
    for side, nm in ((1, "l"), (-1, "r")):
        hip = Vector(P["pelvis_pos"]) + Rp @ Vector(B.HIP if side > 0 else (-B.HIP[0], B.HIP[1], B.HIP[2]))
        fx, fy, splay = P[f"foot_{nm}"]
        ankle = Vector((fx, fy, B.ANKLE_H))
        Rt, Rs = _solve_leg(hip, ankle, side)
        Rf = Euler((0, 0, math.radians(splay)), "XYZ").to_matrix()
        part(f"thigh_{nm}").rotation_euler = (Rp.inverted() @ Rt).to_euler("XYZ")
        part(f"shin_{nm}").rotation_euler = (Rt.inverted() @ Rs).to_euler("XYZ")
        part(f"foot_{nm}").rotation_euler = (Rs.inverted() @ Rf).to_euler("XYZ")
    bpy.context.view_layer.update()
    low = min((o.matrix_world @ v.co).z for k in ("foot_l", "foot_r") for o in (part(k),) for v in o.data.vertices)
    top = max((o.matrix_world @ v.co).z for k in MAKERS for o in (part(k),) for v in o.data.vertices)
    return {"lowest_sole": round(low - root.z, 3), "top": round(top - root.z, 3)}


# ============================================================================ целостность: поиск и подтягивание «летающих» кусков
def _islands(objs):
    """Острова геометрии (связные по общим вершинам) во всех частях, в мировых координатах.
    Возвращает (world_verts, tris, isl) — tris: [(i, j, k, id острова)], isl: [{part, tris, verts}]."""
    wverts, tris, isl = [], [], []
    for o in objs:
        me, M = o.data, o.matrix_world
        base = len(wverts)
        wverts += [M @ v.co for v in me.vertices]
        parent = list(range(len(me.vertices)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for poly in me.polygons:
            vs = list(poly.vertices)
            for v in vs[1:]:
                a, b = find(vs[0]), find(v)
                if a != b:
                    parent[a] = b
        ids = {}
        for poly in me.polygons:
            r = find(poly.vertices[0])
            if r not in ids:
                ids[r] = len(isl)
                isl.append({"part": o.name.replace(NAME + "_", ""), "obj": o, "tris": [], "verts": set()})
            k = ids[r]
            vs = [base + v for v in poly.vertices]
            for i in range(1, len(vs) - 1):
                tris.append((vs[0], vs[i], vs[i + 1], k))
            isl[k]["verts"].update(vs)
    return wverts, tris, isl


def _inside(tree, p):
    """Точка внутри замкнутого тела (чётное/нечётное число пересечений луча по +Z) относительно BVH tree."""
    n, o, d = 0, Vector(p), Vector((0.0, 0.0, 1.0))
    for _ in range(12):
        hit = tree.ray_cast(o, d)
        if hit[0] is None:
            break
        n += 1
        o = hit[0] + d * 1e-5
    return n % 2 == 1


def audit_floating(touch=0.0015, max_snap=0.08, snap=False, embed=0.0012, tangent_push=0.0030):
    """Находит куски (острова) геометрии, плохо связанные с остальной моделью в позе:
      float   — расстояние до остального тела > touch и не внутри другого тела («летает»);
      tangent — касается, но ни одна вершина не заходит внутрь другого тела (держится «на линии», выглядит отдельным).
    snap=True: float сдвигается к ближайшей поверхности (если ближе max_snap) с заглублением embed, tangent вдавливается на tangent_push.
    Возвращает список найденных: {part, tris, kind, dist, center, fixed}."""
    from mathutils.bvhtree import BVHTree
    bpy.context.view_layer.update()
    objs = [part(k) for k in MAKERS]
    offs, acc = {}, 0
    for o in objs:
        offs[o.name] = acc
        acc += len(o.data.vertices)
    wverts, tris, isl = _islands(objs)
    out = []
    for k, it in enumerate(isl):
        rest = [(a, b, c) for a, b, c, i in tris if i != k]
        if not rest:
            continue
        tree = BVHTree.FromPolygons(wverts, rest, epsilon=1e-7)
        vlist = list(it["verts"])
        best = (1e9, None, None)
        n_contact = 0
        for vi in vlist:
            loc = tree.find_nearest(wverts[vi])
            if loc[0] is not None:
                if loc[3] <= touch:
                    n_contact += 1
                if loc[3] < best[0]:
                    best = (loc[3], vi, loc[0])
        dist = best[0]
        step = max(1, len(vlist) // 16)
        n_in = sum(1 for vi in vlist[::step] if _inside(tree, wverts[vi]))
        if dist > touch and n_in:                                    # целиком/частично внутри другого тела — не «летает»
            continue
        if dist <= touch and (n_in or n_contact >= 2):
            continue                                                 # врос в тело или держится ребром (бахрома, заплаты по краю)
        kind = "float" if dist > touch else "tangent"
        c = sum((wverts[v] for v in vlist), Vector()) / len(vlist)
        rec = {"part": it["part"], "tris": sum(1 for t in tris if t[3] == k), "kind": kind, "dist": round(dist, 4),
               "center": tuple(round(x, 3) for x in (c - Vector(DISPLAY_POS))), "fixed": False}
        if snap and dist < max_snap:
            if kind == "float":
                T = best[2] - wverts[best[1]]
                T = T + T.normalized() * embed
            else:
                T = (best[2] - c)
                T = T.normalized() * tangent_push if T.length > 1e-9 else Vector((0, 0, 0))
            o = it["obj"]
            loc_T = o.matrix_world.to_3x3().inverted() @ T
            for vi in vlist:
                o.data.vertices[vi - offs[o.name]].co += loc_T
            o.data.update()
            rec["fixed"] = True
            bpy.context.view_layer.update()
            wverts, tris, _ = _islands(objs)
        out.append(rec)
    return out


# ============================================================================ запекание окклюзии (AO) в цвет граней
def bake_ao(samples=22, dist=0.28, strength=0.72, seed=5):
    """AO по граням: лучи по полусфере на собранной модели в позе; цвет граней множится на (1 − strength·(1 − AO)).
    Двусторонняя ткань и кожа считаются с обеих сторон (берётся более открытая) — внешняя сторона светлее внутренней."""
    import random
    from mathutils.bvhtree import BVHTree
    rnd = random.Random(seed)
    bpy.context.view_layer.update()
    objs = [part(k) for k in MAKERS]
    verts, polys = [], []
    for o in objs:
        M = o.matrix_world
        base = len(verts)
        verts += [M @ v.co for v in o.data.vertices]
        polys += [tuple(base + i for i in p.vertices) for p in o.data.polygons]
    tree = BVHTree.FromPolygons(verts, polys, epsilon=1e-6)
    dirs = []                                                               # косинус-взвешенные направления в локальном кадре (z — по нормали)
    for i in range(samples):
        u, v = (i + 0.5) / samples, (i * 0.618034) % 1.0
        r, th = math.sqrt(u), math.tau * v
        dirs.append(Vector((r * math.cos(th), r * math.sin(th), math.sqrt(max(0.0, 1.0 - u)))))
    done = 0
    for o in objs:
        me = o.data
        attr = me.color_attributes.get("Color")
        if attr is None:
            continue
        M3 = o.matrix_world.to_3x3()
        for poly in me.polygons:
            c = o.matrix_world @ poly.center
            n = (M3 @ poly.normal).normalized()
            best = 0.0
            for sgn in (1.0, -1.0):
                nn = n * sgn
                t = nn.cross(Vector((0, 0, 1)) if abs(nn.z) < 0.9 else Vector((1, 0, 0))).normalized()
                b = nn.cross(t)
                rot = rnd.uniform(0, math.tau)
                cr, sr = math.cos(rot), math.sin(rot)
                hits = 0
                for d in dirs:
                    dx, dy = d.x * cr - d.y * sr, d.x * sr + d.y * cr
                    w = t * dx + b * dy + nn * d.z
                    if tree.ray_cast(c + nn * 0.004, w, dist)[0] is not None:
                        hits += 1
                best = max(best, 1.0 - hits / samples)
            f = 1.0 - strength * (1.0 - best)
            for li in poly.loop_indices:
                col = attr.data[li].color
                attr.data[li].color = (col[0] * f, col[1] * f, col[2] * f, col[3])
        done += len(me.polygons)
    return done


# ============================================================================ просмотр
VIEWS = {"front": (0, 90), "side": (-90, 90), "back": (180, 90), "q": (-35, 86), "qb": (-145, 86), "top": (0, 30)}


def shot(name="front", dist=3.2, center=None):
    """Ставит вид в окне Blender; снимок — отдельным вызовом get_screenshot_of_area_as_image."""
    yaw, pitch = VIEWS[name]
    c = Vector(DISPLAY_POS) + Vector(center or (0, 0, 0.85))
    Z.focus(c, dist, yaw=yaw, pitch=pitch)


def isolate(on=True):
    """Показать только зомби (остальное скрыть во вьюпорте и в рендере на время работы); on=False — вернуть всё как было."""
    for o in bpy.data.objects:
        mine = o.name == NAME or o.name.startswith(NAME + "_") or o.name.startswith("zview_")
        if on:
            o.hide_set(not mine)
            o.hide_render = not mine
        else:
            if not o.name.startswith("zview_"):
                o.hide_set(False)
                o.hide_render = False


def export():
    import props_kit
    return props_kit.export(NAME)
