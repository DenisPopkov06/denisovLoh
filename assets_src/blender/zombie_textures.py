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
SKIN_PALETTE = [(0.60, 0.55, 0.40), (0.64, 0.58, 0.44), (0.55, 0.53, 0.42), (0.50, 0.43, 0.33), (0.61, 0.57, 0.45)]
CLOTH_PALETTE = [(0.42, 0.31, 0.22), (0.34, 0.25, 0.18), (0.49, 0.37, 0.26), (0.37, 0.31, 0.24), (0.28, 0.21, 0.15)]


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


def voronoi(rng, cells, size=SIZE, jitter=0.85):
    """Бесшовные ячейки: расстояния до ближайшей (d1) и второй (d2) точек и номер ближайшей."""
    pts = (np.stack(np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij"), -1) + 0.5
           + (rng.random((cells, cells, 2)) - 0.5) * jitter) / cells                  # [ix, iy] → (x, y)
    ys, xs = (np.mgrid[0:size, 0:size] + 0.5) / size
    cx, cy = (xs * cells).astype(int), (ys * cells).astype(int)
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
    rng = np.random.default_rng(seed)
    d1, d2, ident = voronoi(rng, 14)
    cell_rand = np.random.default_rng(seed + 1).random(196)[ident]
    big = fbm(rng, 3, 3)                                                  # крупные камуфляжные пятна
    big = np.clip((big - 0.5) * 1.3 + 0.5, 0, 1)
    t = np.clip(big * 0.75 + cell_rand * 0.25, 0, 1)                       # ячейка слегка «сдвигает» тон
    col = _palette_color(SKIN_PALETTE, t) * (0.93 + 0.12 * cell_rand)[..., None]
    edge = np.clip((d2 - d1) * 11.0, 0, 1)                                # 0 на границе ячеек
    col *= (0.95 + 0.05 * _smoothstep(0.0, 0.5, edge))[..., None]
    grain = fbm(rng, 24, 2)
    col *= (0.93 + 0.14 * grain)[..., None]
    dirt = np.clip((fbm(rng, 5, 3) - 0.60) * 3, 0, 1)                     # грязь и синюшные пятна
    col = col * (1 - 0.35 * dirt[..., None]) + np.array((0.22, 0.20, 0.20)) * 0.35 * dirt[..., None]
    height = 0.55 * cell_rand + 0.9 * _smoothstep(0.0, 0.6, edge) + 0.25 * grain
    nrm = _normal_from_height(height, 0.10)
    rough = np.clip(0.80 + 0.10 * (cell_rand - 0.5) - 0.10 * edge + 0.05 * grain, 0.5, 1.0)
    ao = 0.70 + 0.30 * _smoothstep(0.0, 0.6, edge)
    return np.clip(col, 0, 1), nrm, ao, rough


def cloth_set(seed=23):
    rng = np.random.default_rng(seed)
    d1, d2, ident = voronoi(rng, 10, jitter=0.9)
    cell_rand = np.random.default_rng(seed + 1).random(100)[ident]
    big = fbm(rng, 3, 4)
    t = np.clip((big - 0.5) * 1.5 + 0.5, 0, 1) * 0.80 + cell_rand * 0.20
    col = _palette_color(CLOTH_PALETTE, t)
    ys, xs = np.mgrid[0:SIZE, 0:SIZE] / SIZE
    weave = 0.5 + 0.5 * np.sin(xs * 2 * np.pi * 24) * np.sin(ys * 2 * np.pi * 24)      # лёгкое плетение (мельче — даёт муар)
    wear = fbm(rng, 6, 4)
    col *= (0.92 + 0.05 * weave + 0.14 * wear)[..., None]
    stain = np.clip((fbm(rng, 4, 3) - 0.56) * 4, 0, 1)                     # бурые пятна и грязь
    col = col * (1 - 0.5 * stain[..., None]) + np.array((0.16, 0.08, 0.05)) * 0.5 * stain[..., None]
    edge = np.clip((d2 - d1) * 12.0, 0, 1)                                 # складки — границы ячеек
    col *= (0.93 + 0.07 * _smoothstep(0.0, 0.5, edge))[..., None]
    height = 0.3 * weave + 0.4 * _smoothstep(0.0, 0.5, edge) + 0.4 * wear
    nrm = _normal_from_height(height, 0.08)
    rough = np.clip(0.90 + 0.06 * (wear - 0.5) - 0.06 * stain, 0.6, 1.0)
    ao = 0.72 + 0.28 * _smoothstep(0.0, 0.5, edge)
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
    """mat_zombie_skin / cloth (текстура × цвет вершин), mat_zombie_misc (цвет вершин: кости, зубы, металл), mat_zombie_eyes."""
    skin = Z.tile_material("mat_zombie_skin", "zombie_skin", culling=True, vcolor=True)
    cloth = Z.tile_material("mat_zombie_cloth", "zombie_cloth", culling=False, vcolor=True)
    misc = Z.flat_material("mat_zombie_misc", rough=0.8, vcolor=True)
    eyes = Z.flat_material("mat_zombie_eyes", (0.66, 0.76, 0.56), rough=0.5, emission=((0.66, 0.76, 0.56), 1.5))
    return [skin, cloth, misc, eyes]
