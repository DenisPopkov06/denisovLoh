import { describe, expect, it } from "vitest";
import { GridPathfinder } from "@/systems/ZombiePathfinder";

// Стена вдоль X на z≈0 от x=-5 до x=2 — обойти можно только справа (x > 2).
const wall = (x: number, z: number): boolean => Math.abs(z) < 0.6 && x > -5.5 && x < 2.5;

describe("GridPathfinder", () => {
  it("returns just the goal when the straight line is clear", () => {
    const pf = new GridPathfinder(0.5);
    const path = pf.findPath({ x: 0, z: -4 }, { x: 0, z: -1 }, () => false);
    expect(path).not.toBeNull();
    expect(path![path!.length - 1]).toEqual({ x: 0, z: -1 });
    expect(path!.length).toBe(1);
  });

  it("routes around a wall through the gap and never through it", () => {
    const pf = new GridPathfinder(0.5);
    const from = { x: 0, z: -4 };
    const to = { x: 0, z: 4 };
    const path = pf.findPath(from, to, wall)!;
    expect(path).not.toBeNull();
    expect(path[path.length - 1]).toEqual(to);
    // Обход идёт через проход справа от стены.
    expect(Math.max(...path.map((p) => p.x))).toBeGreaterThanOrEqual(2.5);
    // Ни один отрезок пути не пересекает стену.
    let prev = from;
    for (const p of path) {
      expect(pf.isSegmentClear(prev, p, wall)).toBe(true);
      prev = p;
    }
  });

  it("returns null when the goal is sealed off", () => {
    const pf = new GridPathfinder(0.5, 2000);
    const ring = (x: number, z: number): boolean => {
      const r = Math.hypot(x, z);
      return r > 2 && r < 3;
    };
    expect(pf.findPath({ x: 0, z: -6 }, { x: 0, z: 0 }, ring)).toBeNull();
  });
});
