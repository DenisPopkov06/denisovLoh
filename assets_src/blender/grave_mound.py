"""Земляной холмик у надгробия: ОДНА форма на всё.

Её берут три места, чтобы надгробие и закопанная земля читались единым целым и совпадали до сантиметра:
  - zone_lib.build_mounds()           — геометрия холмика в модели зоны;
  - zone_textures.ground_unique()     — пятно грунта на карте земли под ним;
  - этот файл как скрипт              — высота (position.y) предметов, лежащих на холмике, в layout.json.

Холмик — вытянутый покатый горб от надгробия вперёд (в сторону «лица»): голова во всю ширину упирается в цоколь и
уходит под него (первая ступень цоколя ≈ 0.10–0.12 м полностью в земле — камень растёт из холмика), к ногам
сужается и скругляется, у самого края плавно сходит на нет (без стенки).

Локальные координаты — как у надгробия в layout.json: u — вперёд от его центра, v — вправо, метры.
Запуск (чистый Python, без Blender):  python assets_src/blender/grave_mound.py  — расставляет y предметов на холмиках.
"""
import json
import math
import os

import numpy as np

U_BACK = -0.30        # самый задний край (за надгробием; скрыт цоколем и скруглён)
U_HEAD = 0.05         # отсюда вперёд холмик во всю ширину
U_FOOT = 2.10         # дальний край у «ног»
BACK_ROUND = U_HEAD - U_BACK
FOOT_ROUND = 0.60     # последние 0.6 м сужаются скруглением
FOOT_W = 0.78         # полуширина у ног — доля от полуширины у головы
H_HEAD = 0.14         # высота гребня у головы (м), от неё вся форма считается; к ногам ниже на 40 %
H_TAPER = 0.40
EMBED = 0.014         # на столько вся поверхность утоплена в землю: край холмика уходит под плоскость земли
HALF_W = {"cross": 0.54, "arch": 0.60, "slab": 0.60}     # полуширина у головы по типам надгробий

_HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT = os.path.join(_HERE, "..", "..", "src", "levels", "zone_old_cemetery", "layout.json")
ITEM_PREFIXES = ("pot_", "wreath_", "flowers_", "vase_")      # лежат/стоят на земле → встают на холмик


def kind_of(object_id):
    """gravestone_arch_a → arch (для tilted/broken-вариантов тоже: они стоят на том же холмике)."""
    for k in HALF_W:
        if f"_{k}_" in object_id:
            return k
    return "arch"


def _round(u):
    """Скругление концов: множитель 0..1 к ширине (эллипс) — на заднем краю и у ног."""
    u = np.asarray(u, float)
    kb = np.clip((U_HEAD - u) / BACK_ROUND, 0.0, 1.0)
    kf = np.clip((u - (U_FOOT - FOOT_ROUND)) / FOOT_ROUND, 0.0, 1.0)
    inside = (u > U_BACK) & (u < U_FOOT)
    return np.sqrt(np.clip(1 - kb ** 2, 0, 1)) * np.sqrt(np.clip(1 - kf ** 2, 0, 1)) * inside


def half_width(u, wh):
    """Полуширина холмика на расстоянии u от центра надгробия; wh — полуширина у головы."""
    u = np.asarray(u, float)
    t = np.clip((u - U_HEAD) / (U_FOOT - U_HEAD), 0.0, 1.0)
    return wh * (1 - (1 - FOOT_W) * t ** 1.2) * _round(u)


def height(u, v, wh):
    """Высота поверхности холмика над землёй (м), без утопления EMBED; 0 вне холмика."""
    u, v = np.asarray(u, float), np.asarray(v, float)
    w = half_width(u, wh)
    rr = _round(u)
    r = np.where(w > 1e-6, np.abs(v) / np.maximum(w, 1e-6), 1.0)
    t = np.clip((u - U_HEAD) / (U_FOOT - U_HEAD), 0.0, 1.0)
    p = 2.4 + 2.6 * (1 - t) ** 1.5                                  # у головы плоский верх (закрывает цоколь), к ногам круглее
    cross = np.clip(1 - r ** p, 0.0, 1.0) ** 1.2                    # нулевой наклон у края — мягкий переход в землю
    return H_HEAD * (1 - H_TAPER * t) * cross * rr ** 0.8


def surface_z(u, v, wh):
    """Высота над плоскостью земли с утоплением: >0 только там, где холмик реально торчит из земли."""
    return np.maximum(height(u, v, wh) - EMBED, 0.0)


def to_local(px, py, gx, gy, fx, fy):
    """Мировая точка (Blender x, y) → (u, v) холмика надгробия (gx, gy) с направлением «лица» (fx, fy)."""
    dx, dy = px - gx, py - gy
    return dx * fx + dy * fy, -dx * fy + dy * fx


def graves_from_layout(objects):
    """[(x, y_blender, fx, fy, полуширина у головы)] — y Blender = −z игры, «лицо» = (sin a, −cos a)."""
    out = []
    for o in objects:
        if o["objectId"].startswith("gravestone"):
            a = math.radians(o["rotationY"])
            out.append((o["position"]["x"], -o["position"]["z"], math.sin(a), -math.cos(a),
                        HALF_W[kind_of(o["objectId"])]))
    return out


def ground_y(objects, x, z):
    """Высота земли в точке игры (x, z): максимум по холмикам, 0 вне них."""
    best = 0.0
    for gx, gy, fx, fy, wh in graves_from_layout(objects):
        if math.hypot(x - gx, -z - gy) > U_FOOT + 0.8:
            continue
        u, v = to_local(x, -z, gx, gy, fx, fy)
        best = max(best, float(surface_z(u, v, wh)))
    return best


def sync_items(write=True):
    """Предметы на земле (горшки, венки, цветы) встают на холмик: position.y = высота поверхности под ними."""
    path = os.path.abspath(LAYOUT)
    raw = open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"                    # перевод строк файла не трогаем
    data = json.loads(raw)
    changed = []
    for o in data["objects"]:
        if not o["objectId"].startswith(ITEM_PREFIXES):
            continue
        y = round(ground_y(data["objects"], o["position"]["x"], o["position"]["z"]), 3)
        if abs(o["position"]["y"] - y) > 1e-9:
            changed.append((o["instanceId"], o["position"]["y"], y))
            o["position"]["y"] = y
    if write and changed:
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text.replace("\n", eol))
    return changed


if __name__ == "__main__":
    for iid, old, new in sync_items():
        print(f"{iid}: y {old} -> {new}")
