"""Текстуры и материалы зомби: кожа и ткань — бесшовные PBR-наборы (albedo sRGB + normal OpenGL + ORM) в духе арт-листа:
ячеистый («гранёный») камуфляж приглушённых оливково-серо-бурых тонов, тёплый свет фонарей.

    import zombie_textures as ZT; ZT.make_textures(); ZT.make_materials()

Каждый набор — 512×512, повторяется на модели каждые TILE метров (zombie_geo.TILE). Файлы — assets_src/textures_src/zombie_*.jpg.
"""
import os

import bpy
import numpy as np

import zone_lib as Z

SIZE = 512
# кожа — камуфляж чётких плоских ячеек: хаки, песочный, оливковый, тёмно-оливковый, бурый, почти чёрно-бурый (sRGB, вес)
SKIN_CELLS = [((0.60, 0.54, 0.43), 0.34), ((0.66, 0.59, 0.47), 0.20), ((0.55, 0.50, 0.39), 0.22), ((0.47, 0.44, 0.34), 0.12),
              ((0.40, 0.32, 0.25), 0.09), ((0.25, 0.20, 0.15), 0.03)]
CLOTH_PALETTE = [(0.38, 0.31, 0.26), (0.30, 0.25, 0.21), (0.45, 0.37, 0.30), (0.34, 0.31, 0.29), (0.24, 0.20, 0.17)]


def _smoothstep(a, b, x):
    k = np.clip((x - a) / (b - a), 0, 1)
    return k * k * (3 - 2 * k)


def value_noise(rng, res, size=SIZE):
    """Бесшовный value-noise 0…1 с решёткой res×res."""
    lat = rng.random((res, res))
    ys, xs = (np.mgrid[0:size, 0:size] + 0.5) / size * res
    x0, y0 = np.floor(xs).astype(int), np.floor(ys).astype(int)
    fx, fy = _smoothstep(0, 1, xs - x0), _smoothstep(0, 1, ys - y0)
    x0, y0, x1, y1 = x0 % res, y0 % res, (x0 + 1) % res, (y0 + 1) % res
    top = lat[y0, x0] * (1 - fx) + lat[y0, x1] * fx
    bot = lat[y1, x0] * (1 - fx) + lat[y1, x1] * fx
    return top * (1 - fy) + bot * fy


def fbm(rng, base, octaves=4, size=SIZE):
    out, amp, tot = np.zeros((size, size)), 1.0, 0.0
    for o in range(octaves):
        out += amp * value_noise(rng, base * 2 ** o, size)
        tot += amp
        amp *= 0.5
    return out / tot


def voronoi(rng, cells, size=SIZE, jitter=0.85, warp=0.0):
    """Бесшовные ячейки: расстояния до ближайшей (d1) и второй (d2) точек и номер ближайшей; warp — искажение границ (рваные края)."""
    pts = (np.stack(np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij"), -1) + 0.5
           + (rng.random((cells, cells, 2)) - 0.5) * jitter) / cells                  # [ix, iy] → (x, y)
    ys, xs = (np.mgrid[0:size, 0:size] + 0.5) / size
    if warp:
        xs = xs + (fbm(rng, 6, 3, size) - 0.5) * warp
        ys = ys + (fbm(rng, 6, 3, size) - 0.5) * warp
    cx, cy = np.floor(xs * cells).astype(int), np.floor(ys * cells).astype(int)
    d1, d2, ident = np.full(xs.shape, 9.0), np.full(xs.shape, 9.0), np.zeros(xs.shape, int)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            nx, ny = (cx + dx) % cells, (cy + dy) % cells
            px = pts[nx, ny, 0] + (cx + dx - nx) / cells
            py = pts[nx, ny, 1] + (cy + dy - ny) / cells
            d = np.hypot(xs - px, ys - py)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d))
            ident = np.where(closer, nx * cells + ny, ident)
            d1 = np.where(closer, d, d1)
    return d1, d2, ident


def _palette_color(pal, t):
    """t 0…1 по палитре (линейная интерполяция)."""
    pal = np.array(pal)
    f = np.clip(t, 0, 0.9999) * (len(pal) - 1)
    i = f.astype(int)
    k = (f - i)[..., None]
    return pal[i] * (1 - k) + pal[i + 1] * k


def _normal_from_height(h, slope):
    """Нормаль (OpenGL) по карте высот; slope — среднеквадратичный наклон (≈ tan угла), независимо от амплитуды высот."""
    hx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5
    hy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5
    k = slope / (np.sqrt(np.mean(hx * hx + hy * hy)) + 1e-9)
    n = np.stack([-hx * k, -hy * k, np.ones_like(h)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def skin_set(seed=11):
    """Албедо: ~7×7 крупных ячеек-плоскостей с чёткими краями, цвет ячейки — из палитры по крупному шуму (пятна кластерами) и случаю."""
    rng = np.random.default_rng(seed)
    cells = 10
    d1, d2, ident = voronoi(rng, cells, jitter=0.9, warp=0.06)
    r = np.random.default_rng(seed + 1)
    cell_rand = r.random(cells * cells)
    big = fbm(rng, 3, 3)
    ys, xs = (np.mgrid[0:SIZE, 0:SIZE] + 0.5) / SIZE
    # шум в центре ячейки: берём среднее по ячейке через ident
    sums = np.bincount(ident.ravel(), weights=big.ravel(), minlength=cells * cells)
    cnt = np.maximum(np.bincount(ident.ravel(), minlength=cells * cells), 1)
    cell_noise = sums / cnt
    score = np.clip((cell_noise - cell_noise.min()) / (np.ptp(cell_noise) + 1e-9) * 0.65 + cell_rand * 0.35, 0, 0.9999)
    w = np.array([c[1] for c in SKIN_CELLS]); w = np.cumsum(w) / w.sum()
    idx = np.searchsorted(w, score)
    pal = np.array([c[0] for c in SKIN_CELLS])
    col = pal[idx[ident]] * (0.94 + 0.12 * r.random(cells * cells)[ident])[..., None]
    grad = fbm(rng, 5, 3)
    col *= (0.95 + 0.10 * grad)[..., None]                                    # лёгкий градиент внутри ячеек
    edge = np.clip((d2 - d1) * 24.0, 0, 1)
    col *= (0.985 + 0.015 * edge)[..., None]                                  # края ячеек почти не видны
    grain = fbm(rng, 40, 2)
    col *= (0.96 + 0.08 * grain)[..., None]
    height = 0.6 * cell_rand[ident] + 0.9 * _smoothstep(0.0, 0.5, edge) + 0.25 * grain
    nrm = _normal_from_height(height, 0.06)
    rough = np.clip(0.62 + 0.14 * (cell_rand[ident] - 0.5) - 0.06 * (1 - edge) + 0.04 * grain, 0.4, 0.9)
    ao = 0.80 + 0.20 * _smoothstep(0.0, 0.6, edge)
    return np.clip(col, 0, 1), nrm, ao, rough


def cloth_set(seed=23):
    """Албедо: тёмная серо-коричневая ткань с пятнами и тонкими трещинками-складками (как образец «Альбедо (одежда)»)."""
    rng = np.random.default_rng(seed)
    d1, d2, ident = voronoi(rng, 10, jitter=0.95, warp=0.05)
    cell_rand = np.random.default_rng(seed + 1).random(100)[ident]
    big = fbm(rng, 3, 4)
    t = np.clip((big - 0.5) * 1.7 + 0.5, 0, 1) * 0.75 + cell_rand * 0.25
    col = _palette_color(CLOTH_PALETTE, t)
    wear = fbm(rng, 6, 4)
    col *= (0.90 + 0.18 * wear)[..., None]
    stain = np.clip((fbm(rng, 4, 3) - 0.58) * 3.5, 0, 1)                      # тёмные пятна грязи
    col = col * (1 - 0.40 * stain[..., None]) + np.array((0.10, 0.07, 0.05)) * 0.40 * stain[..., None]
    edge = np.clip((d2 - d1) * 40.0, 0, 1)                                    # тонкие трещинки по краям ячеек
    vis = 0.35 + 0.65 * fbm(rng, 4, 3)                                         # где-то трещинки заметнее, где-то почти нет
    col *= (1.0 - vis * 0.22 * (1 - edge))[..., None]
    fine = fbm(rng, 48, 2)
    col *= (0.95 + 0.10 * fine)[..., None]
    height = 0.5 * cell_rand + 0.9 * _smoothstep(0.0, 0.4, edge) + 0.3 * wear
    nrm = _normal_from_height(height, 0.07)
    rough = np.clip(0.70 + 0.10 * (wear - 0.5) - 0.05 * stain + 0.05 * (cell_rand - 0.5), 0.5, 0.95)
    ao = 0.75 + 0.25 * _smoothstep(0.0, 0.4, edge)
    return np.clip(col, 0, 1), nrm, ao, rough


def _save(name, rgb):
    """Пишет RGB (0…1, как есть в файле) в JPEG; Non-Color, чтобы значения не пересчитывались."""
    img = bpy.data.images.get(name) or bpy.data.images.new(name, SIZE, SIZE, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    data = np.ones((SIZE, SIZE, 4), np.float32)
    data[..., :3] = rgb
    img.pixels.foreach_set(data.ravel())
    img.filepath_raw = os.path.join(Z.TEX, name)
    img.file_format = "JPEG"
    img.save()
    return img


def make_textures():
    out = {}
    for tile, fn in (("zombie_skin", skin_set), ("zombie_cloth", cloth_set)):
        col, nrm, ao, rough = fn()
        _save(f"{tile}_albedo.jpg", col)
        _save(f"{tile}_normal.jpg", nrm)
        orm = np.stack([ao, rough, np.zeros_like(ao)], -1)               # R = AO, G = roughness, B = metalness
        _save(f"{tile}_orm.jpg", orm)
        out[tile] = os.path.getsize(os.path.join(Z.TEX, f"{tile}_albedo.jpg")) // 1024
    return out


def make_materials():
    """mat_zombie_skin / cloth (текстура × цвет вершин), mat_zombie_misc (цвет вершин: кости, зубы, металл), глаза и их яркая сердцевина."""
    skin = Z.tile_material("mat_zombie_skin", "zombie_skin", culling=True, vcolor=True)
    cloth = Z.tile_material("mat_zombie_cloth", "zombie_cloth", culling=False, vcolor=True)
    misc = Z.flat_material("mat_zombie_misc", rough=0.8, vcolor=True)
    eyes = Z.flat_material("mat_zombie_eyes", (0.05, 0.05, 0.05), rough=0.4, emission=((0.34, 0.37, 0.34), 0.8))
    core = Z.flat_material("mat_zombie_eyes_core", (0.05, 0.05, 0.05), rough=0.4, emission=((0.62, 0.67, 0.62), 0.9))
    return [skin, cloth, misc, eyes, core]
