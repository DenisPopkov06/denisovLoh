"""Земляной холмик у надгробия — ОТДЕЛЬНАЯ модель grave_earth_a.glb (надгробия остаются как были).

Надгробие и земля — две модели, но одна пара: в layout.json у каждого надгробия есть своя земля (grave_earth_a) на ТОЙ ЖЕ
позиции и с тем же поворотом (earth_NNN ↔ grave_NNN). origin модели земли = центр основания камня, «перед» (−Y Blender =
+Z glTF) — туда она и вытянута: ближний конец холмика у лицевой грани цоколя, камень стоит чуть позади выкопанной области.
Земля — обычный декор (без задач, взаимодействия и коллизии): не подсвечивается и не мешает наведению на камень; при
смене состояния камня (сдвинут / упал / разбит) земля остаётся на месте — как и должно быть у могилы.

Вид — прежний (grave_mound.py): низкий неровный эллипсоид с мягким бурым пятном грунта (текстура grave_mound_*.jpg вырезана
из старой карты земли — grave_mound_texture.py). Модель строится в любом открытом .blend (в сцене остаётся не больше, чем было),
из окна Blender (через MCP):

    import sys, importlib; sys.path.insert(0, r"D:\\dev\\denisovLoh\\assets_src\\blender")
    import grave_mound_props as GP; importlib.reload(GP)
    GP.export_earth()                    # → public/models/props/grave_earth_a.glb
"""
import os
import random
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.environ.get("NK_ASSETS", os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import grave_mound as GM  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO, "public", "models", "props")
NAME = "grave_earth_a"
SOIL_MAT = "mat_grave_mound"


def soil_material():
    """Материал земли: PBR из grave_mound_albedo/normal/orm.jpg (те же узлы, что у тайлов зоны)."""
    mat = bpy.data.materials.get(SOIL_MAT)
    if mat is None:
        import zone_lib as Z
        mat = Z.tile_material(SOIL_MAT, "grave_mound")
    return mat


def build_mound(bm, mat_index=0):
    """Добавляет в bm холмик в координатах модели: х — вправо, −у — вперёд (к лицу), z — вверх. Неровный эллипсоид
    (икосфера, вершины чуть сдвинуты шумом), нижняя половина под землёй срезана; UV — окно текстуры grave_mound_*."""
    rnd = random.Random(GM.SEED)
    rx, ry, rz = GM.RADII
    mat = Matrix.Translation((0, -GM.CENTER_U, 0)) @ Matrix.Diagonal((rx, ry, rz, 1))
    res = bmesh.ops.create_icosphere(bm, subdivisions=GM.SUBDIV, radius=1.0, matrix=mat)
    for v in res["verts"]:
        v.co += Vector((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1))) * GM.JITTER
    new_faces = list({f for v in res["verts"] for f in v.link_faces})
    low = [f for f in new_faces if f.calc_center_median().z < GM.CUT_Z]
    bmesh.ops.delete(bm, geom=low, context="FACES")           # нижняя половина под землёй не нужна
    faces = [f for f in new_faces if f.is_valid]
    uv = bm.loops.layers.uv.verify()
    for f in faces:
        f.material_index = mat_index
        f.smooth = True
        for lp in f.loops:
            x, y, _ = lp.vert.co
            lp[uv].uv = ((x + GM.WIN_V) / (2 * GM.WIN_V), 1 - (-y - GM.WIN_U0) / (GM.WIN_U1 - GM.WIN_U0))
    return faces


def make_object(name=NAME):
    """Объект «земля» с материалом в начале координат (временный: export_earth() его удаляет)."""
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)
    bm = bmesh.new()
    build_mound(bm, 0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(soil_material())
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def export_earth(out_dir=None):
    """Строит grave_earth_a и экспортирует в public/models/props/grave_earth_a.glb пресетом night_keeper_glb."""
    import zone_lib as Z
    obj = make_object()
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, NAME + ".glb")
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, **Z.export_settings())
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(mesh)
    return {"glb_kb": os.path.getsize(path) // 1024}
