export interface Point2 {
  x: number;
  z: number;
}

/** (x, z) центра клетки → занята ли она (не пройти зомби такого радиуса). */
export type CellBlockedFn = (x: number, z: number) => boolean;

const SQRT2 = Math.SQRT2;
const NEIGHBOURS: readonly [number, number, number][] = [
  [1, 0, 1], [-1, 0, 1], [0, 1, 1], [0, -1, 1],
  [1, 1, SQRT2], [1, -1, SQRT2], [-1, 1, SQRT2], [-1, -1, SQRT2],
];

class MinHeap {
  private readonly items: { key: number; f: number }[] = [];
  get size(): number {
    return this.items.length;
  }
  push(key: number, f: number): void {
    const items = this.items;
    items.push({ key, f });
    let i = items.length - 1;
    while (i > 0) {
      const parent = (i - 1) >> 1;
      if (items[parent].f <= items[i].f) break;
      [items[parent], items[i]] = [items[i], items[parent]];
      i = parent;
    }
  }
  pop(): number {
    const items = this.items;
    const top = items[0];
    const last = items.pop()!;
    if (items.length > 0) {
      items[0] = last;
      let i = 0;
      for (;;) {
        const l = i * 2 + 1;
        const r = l + 1;
        let m = i;
        if (l < items.length && items[l].f < items[m].f) m = l;
        if (r < items.length && items[r].f < items[m].f) m = r;
        if (m === i) break;
        [items[m], items[i]] = [items[i], items[m]];
        i = m;
      }
    }
    return top.key;
  }
}

/** A* по равномерной сетке в плоскости XZ (8 соседей, диагональ только если обе
 *  прилегающие стороны свободны — не срезаем угол препятствия). Занятость клеток
 *  считается лениво — обходятся только те клетки, что реально нужны поиску, без
 *  заранее построенной карты всей зоны. */
export class GridPathfinder {
  constructor(
    private readonly cellSize = 0.5,
    private readonly maxExpansions = 5000,
  ) {}

  /** Путь от from до to: точки по порядку, последняя — сама to; первую точку
   *  (from) не включает. null — пути нет (или его не нашли за maxExpansions). */
  findPath(from: Point2, to: Point2, isBlocked: CellBlockedFn): Point2[] | null {
    const size = this.cellSize;
    const memo = new Map<number, boolean>();
    const key = (ix: number, iz: number): number => (ix + 32768) * 65536 + (iz + 32768);
    const blocked = (ix: number, iz: number): boolean => {
      const k = key(ix, iz);
      let v = memo.get(k);
      if (v === undefined) {
        v = isBlocked(ix * size, iz * size);
        memo.set(k, v);
      }
      return v;
    };

    const sx = Math.round(from.x / size);
    const sz = Math.round(from.z / size);
    let gx = Math.round(to.x / size);
    let gz = Math.round(to.z / size);
    // Цель внутри занятой клетки (игрок вплотную к надгробию) — идём к ближайшей
    // свободной рядом, последний шаг до самого игрока делает обычное движение.
    if (blocked(gx, gz)) {
      const free = this.nearestFree(gx, gz, blocked, 4);
      if (!free) return null;
      [gx, gz] = free;
    }

    const startKey = key(sx, sz);
    const goalKey = key(gx, gz);
    const g = new Map<number, number>([[startKey, 0]]);
    const cameFrom = new Map<number, number>();
    const coords = new Map<number, [number, number]>([[startKey, [sx, sz]]]);
    const closed = new Set<number>();
    const open = new MinHeap();
    const h = (ix: number, iz: number): number => {
      const dx = Math.abs(ix - gx);
      const dz = Math.abs(iz - gz);
      return Math.max(dx, dz) + (SQRT2 - 1) * Math.min(dx, dz);
    };
    open.push(startKey, h(sx, sz));

    let expansions = 0;
    while (open.size > 0) {
      const current = open.pop();
      if (current === goalKey) return this.buildPath(current, cameFrom, coords, from, to, blocked);
      if (closed.has(current)) continue;
      closed.add(current);
      if (++expansions > this.maxExpansions) return null;

      const [cx, cz] = coords.get(current)!;
      const gCur = g.get(current)!;
      for (const [dx, dz, cost] of NEIGHBOURS) {
        const nx = cx + dx;
        const nz = cz + dz;
        if (blocked(nx, nz)) continue;
        if (dx !== 0 && dz !== 0 && (blocked(cx + dx, cz) || blocked(cx, cz + dz))) continue;
        const nKey = key(nx, nz);
        if (closed.has(nKey)) continue;
        const tentative = gCur + cost;
        if (tentative < (g.get(nKey) ?? Infinity)) {
          g.set(nKey, tentative);
          cameFrom.set(nKey, current);
          coords.set(nKey, [nx, nz]);
          open.push(nKey, tentative + h(nx, nz));
        }
      }
    }
    return null;
  }

  /** Свободна ли прямая от a до b (проверка клеток с шагом в полклетки). */
  isSegmentClear(a: Point2, b: Point2, isBlocked: CellBlockedFn): boolean {
    const size = this.cellSize;
    const dist = Math.hypot(b.x - a.x, b.z - a.z);
    const steps = Math.max(1, Math.ceil(dist / (size * 0.5)));
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      const x = a.x + (b.x - a.x) * t;
      const z = a.z + (b.z - a.z) * t;
      if (isBlocked(Math.round(x / size) * size, Math.round(z / size) * size)) return false;
    }
    return true;
  }

  private nearestFree(
    gx: number,
    gz: number,
    blocked: (ix: number, iz: number) => boolean,
    maxRing: number,
  ): [number, number] | null {
    for (let r = 1; r <= maxRing; r++) {
      for (let dx = -r; dx <= r; dx++) {
        for (let dz = -r; dz <= r; dz++) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== r) continue;
          if (!blocked(gx + dx, gz + dz)) return [gx + dx, gz + dz];
        }
      }
    }
    return null;
  }

  /** Восстанавливает путь и спрямляет его: из каждой точки прыгаем сразу к самой
   *  дальней, до которой прямая свободна, — иначе зомби шёл бы "лесенкой" по клеткам. */
  private buildPath(
    goal: number,
    cameFrom: Map<number, number>,
    coords: Map<number, [number, number]>,
    from: Point2,
    to: Point2,
    blocked: (ix: number, iz: number) => boolean,
  ): Point2[] {
    const size = this.cellSize;
    const cells: Point2[] = [];
    let k: number | undefined = goal;
    while (k !== undefined) {
      const [ix, iz] = coords.get(k)!;
      cells.push({ x: ix * size, z: iz * size });
      k = cameFrom.get(k);
    }
    cells.reverse();
    cells.shift(); // клетка старта
    const lastCell = cells[cells.length - 1];
    if (!lastCell || Math.hypot(lastCell.x - to.x, lastCell.z - to.z) > 1e-6) cells.push({ x: to.x, z: to.z });

    const cellBlocked = (x: number, z: number): boolean => blocked(Math.round(x / size), Math.round(z / size));
    const smoothed: Point2[] = [];
    let anchor = from;
    let i = 0;
    while (i < cells.length) {
      let far = i;
      for (let j = cells.length - 1; j > i; j--) {
        if (this.isSegmentClear(anchor, cells[j], cellBlocked)) {
          far = j;
          break;
        }
      }
      smoothed.push(cells[far]);
      anchor = cells[far];
      i = far + 1;
    }
    return smoothed;
  }
}
