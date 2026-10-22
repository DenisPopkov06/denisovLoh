"""Земляной холмик у надгробия — отдельная модель grave_earth_a.glb, парная к надгробию (не часть модели камня).

В layout.json у каждого надгробия своя земля на той же позиции и с тем же поворотом. Геометрию и экспорт делает
grave_mound_props.py, текстуру — grave_mound_texture.py.

Вид — прежний: низкий неровный эллипсоидный холмик (полуоси 0.44 × 0.98 × 0.14 м, вершины чуть «разбиты» шумом) с
мягким бурым пятном грунта. Камень отставлен назад от выкопанной области: холмик начинается у лицевого края цоколя
(0.15–0.21 м от центра камня) и тянется вперёд. Одна и та же земля для всех надгробий и их вариантов.

Локальные координаты — как у надгробия: u — вперёд от его центра (в сторону «лица»), v — вправо, метры.
"""
CENTER_U = 1.15                    # центр холмика перед камнем: ближний конец (CENTER_U − 0.98 = 0.17) у лицевой грани цоколя
RADII = (0.44, 0.98, 0.14)         # полуоси: поперёк (v), вдоль (u), высота
SUBDIV = 2                         # икосфера: 80 граней (как прежде, ≈ 40 после среза), гладкое затенение
JITTER = 0.02                      # шум вершин, м (неровная земля; тот же для всех надгробий)
SEED = 21
CUT_Z = -0.01                      # грани ниже этого уровня (под землёй) не нужны
# окно текстуры grave_mound_*.jpg в локальных координатах (м): v ∈ ±WIN_V, u ∈ [WIN_U0, WIN_U1]; UV меша — ровно оно
WIN_V = 0.51
WIN_U0, WIN_U1 = 0.14, 2.18


# ----------------------------------------------------------------------------- пары в layout.json
LAYOUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src", "levels", "zone_old_cemetery", "layout.json")
EARTH_ID = "grave_earth_a"


def sync_layout_earth(write=True):
    """У каждого надгробия (grave_NNN) в layout.json своя земля (earth_NNN): та же позиция и поворот. Пересобирает пары
    заново — запускать после любой правки позиций надгробий:  python assets_src/blender/grave_mound.py"""
    path = os.path.abspath(LAYOUT)
    raw = open(path, encoding="utf-8", newline="").read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    data = json.loads(raw)
    objects = [o for o in data["objects"] if o["objectId"] != EARTH_ID]
    pairs = []
    for o in objects:
        if o["objectId"].startswith("gravestone") and o["instanceId"].startswith("grave_"):
            pairs.append({
                "instanceId": "earth_" + o["instanceId"][len("grave_"):],
                "objectId": EARTH_ID,
                "position": dict(o["position"]),
                "rotationY": o["rotationY"],
                "defaultState": "NORMAL",
            })
    data["objects"] = objects + pairs
    if write:
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text.replace("\n", eol))
    return len(pairs)


if __name__ == "__main__":
    print("earth pairs:", sync_layout_earth())
