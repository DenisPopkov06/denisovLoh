import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { ZombieSystem } from "@/systems/ZombieSystem";
import type { SceneManager, CollisionCircle, CollisionRect } from "@/core/SceneManager";
import type { Vec3 } from "@/data/types";
import { ZOMBIE_APPEARS_AT_SHIFT } from "@/systems/DifficultyScaler";

/** Двойник SceneManager — хранит только то, что нужно ZombieSystem (позицию/позу
 *  актёра и коллизии), без реального three.js рендера/загрузки моделей. */
function makeFakeSceneManager(
  circles: CollisionCircle[] = [],
  rects: CollisionRect[] = [],
): SceneManager & { position: Vec3 | null; animationSpeed: number; animation: string | null } {
  const fake = {
    position: null as Vec3 | null,
    animationSpeed: 1,
    animation: null as string | null,
    playZombieAnimation: (name: string) => {
      fake.animation = name;
    },
    spawnZombie: vi.fn(async (position: Vec3) => {
      fake.position = position;
    }),
    removeZombie: vi.fn(() => {
      fake.position = null;
    }),
    isZombieActive: () => fake.position !== null,
    getZombiePosition: () => fake.position,
    setZombiePose: (position: Vec3) => {
      fake.position = position;
    },
    setZombieAnimationSpeed: (scale: number) => {
      fake.animationSpeed = scale;
    },
    getCollisionCircles: () => circles,
    getCollisionRects: () => rects,
  };
  return fake as unknown as SceneManager & { position: Vec3 | null; animationSpeed: number; animation: string | null };
}

describe("ZombieSystem", () => {
  it("spawns away from the player on activate()", async () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    const player = new THREE.Vector3(0, 1.6, 0);

    await zombie.activate(player);

    expect(zombie.isActive()).toBe(true);
    expect(scene.position).not.toBeNull();
    const dx = scene.position!.x - player.x;
    const dz = scene.position!.z - player.z;
    expect(Math.hypot(dx, dz)).toBeGreaterThan(5);
  });

  it("activate() twice is a no-op the second time", async () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    await zombie.activate(new THREE.Vector3(0, 1.6, 0));
    const spawnSpy = scene.spawnZombie as unknown as ReturnType<typeof vi.fn>;
    await zombie.activate(new THREE.Vector3(5, 1.6, 5));
    expect(spawnSpy).toHaveBeenCalledTimes(1);
  });

  it("moves the zombie toward the player each frame", async () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    scene.position = { x: -10, y: 0, z: 0 };
    // Принудительно считаем активным, минуя случайный спавн — see activate() note above.
    (zombie as unknown as { active: boolean }).active = true;

    const player = new THREE.Vector3(0, 1.6, 0);
    const before = scene.position!.x;
    zombie.update(0.1, player, ZOMBIE_APPEARS_AT_SHIFT);
    expect(scene.position!.x).toBeGreaterThan(before);
  });

  it("does not cross a blocking collision circle directly, but still advances around it", async () => {
    const circle: CollisionCircle = { x: -1, z: 0, radius: 0.6, vaultable: false };
    const scene = makeFakeSceneManager([circle]);
    const zombie = new ZombieSystem(scene);
    scene.position = { x: -10, y: 0, z: 0 };
    (zombie as unknown as { active: boolean }).active = true;

    const player = new THREE.Vector3(0, 1.6, 0);
    for (let i = 0; i < 50; i++) zombie.update(0.1, player, ZOMBIE_APPEARS_AT_SHIFT);

    // Не должен был оказаться внутри круга-коллайдера.
    const dx = scene.position!.x - circle.x;
    const dz = scene.position!.z - circle.z;
    expect(Math.hypot(dx, dz)).toBeGreaterThanOrEqual(circle.radius);
  });

  it("speeds up with shiftIndex but stays below the player's base walk speed of 3 m/s", async () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    scene.position = { x: -10, y: 0, z: 0 };
    (zombie as unknown as { active: boolean }).active = true;
    const player = new THREE.Vector3(0, 1.6, 0);

    zombie.update(1, player, ZOMBIE_APPEARS_AT_SHIFT);
    const traveledAtShift4 = scene.position!.x - -10;

    scene.position = { x: -10, y: 0, z: 0 };
    zombie.update(1, player, ZOMBIE_APPEARS_AT_SHIFT + 10);
    const traveledAtHighShift = scene.position!.x - -10;

    expect(traveledAtHighShift).toBeGreaterThan(traveledAtShift4);
    expect(traveledAtHighShift).toBeLessThan(3);
  });

  it("isWithinAttackRange() is true only at close range", () => {
    const zombie = new ZombieSystem(makeFakeSceneManager());
    expect(zombie.isWithinAttackRange(0.5)).toBe(true);
    expect(zombie.isWithinAttackRange(5)).toBe(false);
  });

  it("deactivate() removes the zombie and update() reports no distance afterwards", async () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    await zombie.activate(new THREE.Vector3(0, 1.6, 0));

    zombie.deactivate();
    expect(zombie.isActive()).toBe(false);
    expect(scene.position).toBeNull();
    expect(zombie.update(0.1, new THREE.Vector3(), ZOMBIE_APPEARS_AT_SHIFT)).toBe(Infinity);
  });

  it("stops and plays the attack clip when the player is in reach, walks again once they back off", () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    scene.position = { x: -0.8, y: 0, z: 0 };
    (zombie as unknown as { active: boolean }).active = true;
    const player = new THREE.Vector3(0, 1.6, 0);

    zombie.update(0.1, player, ZOMBIE_APPEARS_AT_SHIFT);
    expect(scene.animation).toBe("attack");
    expect(scene.position!.x).toBe(-0.8);

    // Чуть дальше ATTACK_RANGE — всё ещё бьёт (гистерезис, без дёрганья клипов).
    scene.position = { x: -1.3, y: 0, z: 0 };
    zombie.update(0.1, player, ZOMBIE_APPEARS_AT_SHIFT);
    expect(scene.animation).toBe("attack");

    scene.position = { x: -3, y: 0, z: 0 };
    zombie.update(0.1, player, ZOMBIE_APPEARS_AT_SHIFT);
    expect(scene.animation).toBe("walk");
    expect(scene.position!.x).toBeGreaterThan(-3);
  });

  it("kill() plays the death clip, then the zombie neither moves nor reports a distance", () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    scene.position = { x: -5, y: 0, z: 0 };
    (zombie as unknown as { active: boolean }).active = true;

    zombie.kill();
    expect(zombie.isDead()).toBe(true);
    expect(scene.animation).toBe("death");
    expect(zombie.update(0.1, new THREE.Vector3(0, 1.6, 0), ZOMBIE_APPEARS_AT_SHIFT)).toBe(Infinity);
    expect(scene.position!.x).toBe(-5);
  });

  it("a zombie spawned after a kill chases again", async () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    await zombie.activate(new THREE.Vector3(0, 1.6, 0));
    zombie.kill();
    zombie.deactivate();

    await zombie.activate(new THREE.Vector3(0, 1.6, 0));
    expect(zombie.isDead()).toBe(false);
    expect(zombie.update(0.1, new THREE.Vector3(0, 1.6, 0), ZOMBIE_APPEARS_AT_SHIFT)).toBeLessThan(Infinity);
  });

  it("moves along Z as well as X (player straight ahead on the Z axis)", () => {
    const scene = makeFakeSceneManager();
    const zombie = new ZombieSystem(scene);
    scene.position = { x: 0, y: 0, z: -10 };
    (zombie as unknown as { active: boolean }).active = true;

    zombie.update(0.5, new THREE.Vector3(0, 1.6, 0), ZOMBIE_APPEARS_AT_SHIFT);
    expect(scene.position!.z).toBeGreaterThan(-10);
  });
});
