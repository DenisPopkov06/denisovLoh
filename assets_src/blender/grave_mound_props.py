"""Земляной холмик внутри моделей надгробий: камень + земля — ОДНА сущность (один .glb, один узел).

Куда игра поставит (перемешает, подвинет, подменит вариантом) надгробие — туда уедет и холмик; в модели зоны
и на карте земли холмиков нет. Вид — прежний (grave_mound.py): низкий неровный эллипсоид с мягким бурым пятном грунта
(текстура grave_mound_*.jpg вырезана из старой карты земли — grave_mound_texture.py).
Холмик — второй материал той же модели (primitive; материал помечен extras nk_highlight = "earth" — игра подсвечивает
землю и камень по отдельности), камень остаётся с запечённым атласом; origin и «перед» (−Y Blender =
+Z glTF) те же, что у камня, холмик вытянут вперёд от лицевой грани.

Работает с props_cemetery.blend (его пишет bake_props.py — там add_mound() вызывается после запекания, так что
пересборка пропсов сохраняет холмики). Из окна Blender (через MCP), в отдельных вызовах:

    import sys, importlib; sys.path.insert(0, r"D:\\dev\\denisovLoh\\assets_src\\blender")
    import grave_mound_props as GP; importlib.reload(GP)
    GP.open_props()                      # 1) открыть props_cemetery.blend (в своём вызове)
    GP.export_all(save=True)             # 2) холмик во все надгробия → public/models/props/gravestone_*.glb
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
TEX = os.path.join(REPO, "assets_src", "textures_src")
OUT_DIR = os.path.join(REPO, "public", "models", "props")
PROPS_BLEND = os.path.join(HERE, "props_cemetery.blend")
SOIL_MAT = "mat_grave_mound"
# extras материала → material.userData в three.js: InteractionSystem подсвечивает землю и камень ПО ОТДЕЛЬНОСТИ
# (меши с этим тегом — отдельная часть объекта; взаимодействие с надгробием остаётся целиком)
HIGHLIGHT_KEY, HIGHLIGHT_PART = "nk_highlight", "earth"

GRAVESTONES = [
    "gravestone_cross_a", "gravestone_arch_a", "gravestone_slab_a",
    "gravestone_cross_broken_a", "gravestone_slab_broken_a", "gravestone_rubble_a", "gravestone_arch_broken_a",
    "gravestone_cross_tilted_a", "gravestone_arch_tilted_a", "gravestone_headstone_tilted_a",
]


def soil_material():
    """Материал земли: PBR из grave_mound_albedo/normal/orm.jpg (те же узлы, что у тайлов зоны).
    Уже созданный переиспользуется (пересоздание оставило бы пустые слоты у мешей, где он уже стоит)."""
    mat = bpy.data.materials.get(SOIL_MAT)
    if mat is None:
        import zone_lib as Z
        mat = Z.tile_material(SOIL_MAT, "grave_mound")
    mat[HIGHLIGHT_KEY] = HIGHLIGHT_PART
    return mat


def build_mound(bm, mat_index):
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


def has_mound(obj):
    return any(m and m.name == SOIL_MAT for m in obj.data.materials)


def add_mound(obj, soil=None):
    """Холмик в меш надгробия вторым материалом. Идемпотентно: повторный вызов ничего не меняет."""
    if has_mound(obj):
        return False
    soil = soil or bpy.data.materials.get(SOIL_MAT) or soil_material()
    obj.data.materials.append(soil)
    idx = len(obj.data.materials) - 1
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    build_mound(bm, idx)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return True


def remove_mound(obj):
    """Убирает холмик (все грани со вторым и следующими материалами и их слоты) — остаётся чистый камень."""
    if len(obj.data.materials) < 2:
        return False
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index > 0], context="FACES")
    bm.to_mesh(obj.data)
    bm.free()
    while len(obj.data.materials) > 1:
        obj.data.materials.pop(index=len(obj.data.materials) - 1)
    obj.data.update()
    return True


def open_props():
    """Открывает props_cemetery.blend; картинки с чужими путями (на машине автора) перепривязывает к textures_src."""
    bpy.ops.wm.open_mainfile(filepath=PROPS_BLEND)


def fix_image_paths():
    fixed = 0
    for im in bpy.data.images:
        if im.source == "FILE" and im.filepath and not os.path.exists(bpy.path.abspath(im.filepath)):
            p = os.path.join(TEX, os.path.basename(im.filepath.replace("\\", "/")))
            if os.path.exists(p):
                im.filepath = p
                im.reload()
                fixed += 1
    return fixed


def export_all(names=None, save=False, out_dir=None):
    """Холмик во все надгробия (если ещё нет) и экспорт каждого в public/models/props/<имя>.glb пресетом night_keeper_glb.
    Модель экспортируется в начале координат (в сцене они лежат рядами для просмотра)."""
    import zone_lib as Z
    fix_image_paths()
    names = names or GRAVESTONES
    soil = soil_material()
    settings = Z.export_settings()
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    res = {}
    for n in names:
        obj = bpy.data.objects[n]
        add_mound(obj, soil)
        loc = obj.location.copy()
        obj.location = (0, 0, 0)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = os.path.join(out_dir, n + ".glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, **settings)
        obj.location = loc
        res[n] = os.path.getsize(path) // 1024
    if save:
        bpy.ops.wm.save_mainfile()
    return res
