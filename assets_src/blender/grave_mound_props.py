"""Земляной холмик внутри моделей надгробий: камень + земля — ОДНА сущность (один .glb, один узел).

Куда игра поставит (перемешает, подвинет, подменит вариантом) надгробие — туда уедет и холмик; в модели зоны
и на карте земли холмиков нет. Форма — grave_mound.py; материал — бесшовный тайл tile_soil (zone_textures.tile_soil).
Холмик — второй материал той же модели (primitive), камень остаётся с запечённым атласом; origin и «перед» (−Y Blender =
+Z glTF) те же, что у камня, холмик вытянут вперёд от лицевой грани.

Работает с props_cemetery.blend (его пишет bake_props.py — там add_mound() вызывается после запекания, так что
пересборка пропсов сохраняет холмики). Из окна Blender (через MCP), в отдельных вызовах:

    import sys, importlib; sys.path.insert(0, r"D:\\dev\\denisovLoh\\assets_src\\blender")
    import grave_mound_props as GP; importlib.reload(GP)
    GP.open_props()                      # 1) открыть props_cemetery.blend (в своём вызове)
    GP.export_all(save=True)             # 2) холмик во все надгробия → public/models/props/gravestone_*.glb
"""
import math
import os
import sys

import bmesh
import bpy

HERE = os.environ.get("NK_ASSETS", os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import grave_mound as GM  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
TEX = os.path.join(REPO, "assets_src", "textures_src")
OUT_DIR = os.path.join(REPO, "public", "models", "props")
PROPS_BLEND = os.path.join(HERE, "props_cemetery.blend")
SOIL_MAT = "mat_tile_soil"
SOIL_TILE_M = 0.9           # бесшовный тайл земли повторяется каждые 0.9 м
NU, NV = 22, 10             # срезов вдоль холмика и ячеек поперёк

GRAVESTONES = [
    "gravestone_cross_a", "gravestone_arch_a", "gravestone_slab_a",
    "gravestone_cross_broken_a", "gravestone_slab_broken_a", "gravestone_rubble_a", "gravestone_arch_broken_a",
    "gravestone_cross_tilted_a", "gravestone_arch_tilted_a", "gravestone_headstone_tilted_a",
]


def soil_material():
    """Материал земли: PBR из tile_soil_albedo/normal/orm.jpg (те же узлы, что у остальных тайлов зоны).
    Уже созданный переиспользуется (пересоздание оставило бы пустые слоты у мешей, где он уже стоит)."""
    mat = bpy.data.materials.get(SOIL_MAT)
    if mat is not None:
        return mat
    import zone_lib as Z
    return Z.tile_material(SOIL_MAT, "tile_soil")


def build_mound(bm, mat_index):
    """Добавляет в bm поверхность холмика в координатах модели: х — вправо, −у — вперёд (к лицу), z — вверх."""
    def at(u, v):
        z = float(GM.height(u, v)) - GM.EMBED                # край утоплен под землю
        return bm.verts.new((v, -u, z))

    us = [GM.U_BACK + (GM.U_FOOT - GM.U_BACK) * (1 - math.cos(math.pi * i / NU)) / 2 for i in range(NU + 1)]
    tail, head = at(us[0], 0.0), at(us[-1], 0.0)             # острые концы: задний край и ноги
    rings = [[at(u, float(GM.half_width(u)) * (2 * j / NV - 1)) for j in range(NV + 1)] for u in us[1:-1]]
    faces = []
    for j in range(NV):
        faces.append(bm.faces.new((tail, rings[0][j + 1], rings[0][j])))
        faces.append(bm.faces.new((head, rings[-1][j], rings[-1][j + 1])))
        for i in range(len(rings) - 1):
            faces.append(bm.faces.new((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j])))
    uv = bm.loops.layers.uv.verify()
    for f in faces:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
        f.material_index = mat_index
        f.smooth = True
        for lp in f.loops:
            x, y, _ = lp.vert.co
            lp[uv].uv = (x / SOIL_TILE_M + 0.37, y / SOIL_TILE_M + 0.61)
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
