"""Текстура земляного холмика: вырезка из ПРЕЖНЕЙ карты земли (там холмик был нарисован пятном грунта).

Пока холмики были запечены в зону, их вид давала карта земли ground_old_cemetery_* (коммит c6628bb): приглушённое
красновато-бурое пятно с мягким краем, зерно, чуть всходов. Когда холмик переехал внутрь моделей надгробий, тот же вид
нужен отдельной текстурой — этот скрипт вырезает её из старой карты (одно из надгробий с поворотом ≈ 0°) в системе
холмика и кладёт в assets_src/textures_src/grave_mound_{albedo,normal,orm}.jpg (128×256: окно 1.02 × 2.04 м).
Запуск (нужны старые карты в каталоге; их даёт `git show c6628bb:assets_src/textures_src/ground_old_cemetery_<k>.jpg`):

    python assets_src/blender/grave_mound_texture.py <каталог со старыми ground_{albedo,normal,orm}.jpg>

Окно текстуры в локальных координатах холмика (м): v ∈ ±WIN_V, u ∈ [WIN_U0, WIN_U1] (u — вперёд от камня).
UV меша — ровно это окно (grave_mound_props.build_mound); строки картинки идут по возрастанию u (сверху вниз).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

import grave_mound as GM

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO, "assets_src", "textures_src")
LAYOUT = os.path.join(REPO, "src", "levels", "zone_old_cemetery", "layout.json")

SOURCE_GRAVE = "grave_034"          # чистое окружение, хорошо читаемое пятно
OLD_CENTER_U = 1.05                 # у старого холмика центр был в 1.05 м перед камнем
W, H = 128, 256
GM_SIZE, GN = 40.0, 2048            # зона 40 м; карта земли 2048² (≈ 2 см на пиксель)


def sample(img, grave, map_px, blur=0):
    """Окно холмика из карты земли map_px × map_px (покрывает ту же зону 40 × 40 м), бикубикой."""
    gx, gy = grave["position"]["x"], -grave["position"]["z"]
    a = math.radians(grave["rotationY"])
    fx, fy = math.sin(a), -math.cos(a)                       # «лицо» в координатах Blender
    cx, cy = gx + fx * OLD_CENTER_U, gy + fy * OLD_CENTER_U   # центр старого холмика
    du = (GM.WIN_U1 - GM.WIN_U0) / H
    dv = 2 * GM.WIN_V / W
    k = map_px / GM_SIZE                                     # пикселей карты на метр

    def to_px(u, v):
        x = cx + fx * (u - GM.CENTER_U) - fy * v
        y = cy + fy * (u - GM.CENTER_U) + fx * v
        return (x + GM_SIZE / 2) * k, map_px - (y + GM_SIZE / 2) * k

    u0, v0 = GM.WIN_U0 + du / 2, -GM.WIN_V + dv / 2           # центр пикселя (0, 0)
    p00 = np.array(to_px(u0, v0))
    pcol = np.array(to_px(u0, v0 + dv)) - p00                # шаг на пиксель вправо
    prow = np.array(to_px(u0 + du, v0)) - p00                # шаг на пиксель вниз
    # аффин PIL: вход = (a·(x+½) + b·(y+½) + c, d·(x+½) + e·(y+½) + f) для пикселя вывода (x, y)
    c, f = p00 - 0.5 * (pcol + prow)
    data = (pcol[0], prow[0], c, pcol[1], prow[1], f)
    src = img.filter(ImageFilter.MedianFilter(blur)) if blur else img
    return src.transform((W, H), Image.AFFINE, data, resample=Image.BICUBIC)


def main(src_dir):
    layout = json.load(open(LAYOUT, encoding="utf-8"))["objects"]
    grave = next(o for o in layout if o["instanceId"] == SOURCE_GRAVE)
    os.makedirs(OUT_DIR, exist_ok=True)
    for kind, blur in (("albedo", 3), ("normal", 0), ("orm", 0)):
        img = Image.open(os.path.join(src_dir, f"ground_{kind}.jpg")).convert("RGB")
        out = sample(img, grave, img.width, blur)
        out.save(os.path.join(OUT_DIR, f"grave_mound_{kind}.jpg"), quality=92)
        print("grave_mound_" + kind, out.size)


if __name__ == "__main__":
    main(sys.argv[1])
