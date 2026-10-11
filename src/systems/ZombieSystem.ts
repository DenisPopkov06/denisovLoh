import * as THREE from "three";
import type { Vec3 } from "@/data/types";
import type { SceneManager, CollisionCircle, CollisionRect } from "@/core/SceneManager";
import { ZOMBIE_APPEARS_AT_SHIFT } from "@/systems/DifficultyScaler";

// Игрок ходит со скоростью 3 м/с (PlayerController.moveSpeed) и может спринтовать
// (×1.6 = 4.8 м/с) — зомби на старте заметно медленнее, чтобы от него можно было
// просто уйти быстрым шагом, и разгоняется со сменами ("с левелом ускоряется"),
// но без спринта игрок уже не всегда сможет держать дистанцию. SPEED_CAP не выше
// обычного шага игрока — спринт остаётся надёжным способом оторваться на любой смене.
const BASE_SPEED = 1.5;
const SPEED_PER_SHIFT = 0.18;
const SPEED_CAP = 2.8;
const ZOMBIE_RADIUS = 0.35;
// "Слишком близко" — чуть больше суммы радиусов игрока и зомби (PLAYER_RADIUS=0.35
// в PlayerController), чтобы урон начинался от физического контакта, а не впритык.
const ATTACK_RANGE = 1.1;
const DAMAGE_PER_SECOND = 22;
// Высоты лучей коллизии (см. ZombieSystem.isBlocked) — аналог двух уровней
// PlayerController (глаза/низкий), но от роста зомби (~1.75м, см. SESSION_SUMMARY.md),
// а не от камеры: ловит стволы деревьев/столбы и более низкие препятствия разом.
const HIGH_RAY_HEIGHT = 1.4;
const LOW_RAY_HEIGHT = 0.5;
// Зомби не спавнится прямо на игроке — на таком расстоянии от его текущей позиции,
// в случайном направлении, с несколькими попытками уйти от занятых мест (надгробия,
// забор) — см. findSpawnPosition.
const SPAWN_DISTANCE = 10;
const SPAWN_ATTEMPTS = 12;
const EMPTY_CIRCLES: readonly CollisionCircle[] = [];
const EMPTY_RECTS: readonly CollisionRect[] = [];
const EMPTY_MESHES: readonly THREE.Object3D[] = [];
const EMPTY_EXCLUDED: ReadonlySet<THREE.Object3D> = new Set();

function isPositionBlocked(
  x: number,
  z: number,
  radius: number,
  circles: readonly CollisionCircle[],
  rects: readonly CollisionRect[],
): boolean {
  for (const circle of circles) {
    const dx = x - circle.x;
    const dz = z - circle.z;
    const minDist = circle.radius + radius;
    if (dx * dx + dz * dz < minDist * minDist) return true;
  }
  for (const rect of rects) {
    const nearX = THREE.MathUtils.clamp(x, rect.minX, rect.maxX);
    const nearZ = THREE.MathUtils.clamp(z, rect.minZ, rect.maxZ);
    const dx = x - nearX;
    const dz = z - nearZ;
    if (dx * dx + dz * dz < radius * radius) return true;
  }
  return false;
}

/** Зомби (моб-преследователь, появляется с ZOMBIE_APPEARS_AT_SHIFT): идёт к игроку
 *  по кратчайшему пути в плоскости XZ, обходя ту же коллизию, что и игрок (надгробия,
 *  ограда, статическая геометрия зоны), не проходит сквозь объекты, разгоняется со
 *  сменами и отнимает жизни игрока (HealthSystem), если подойти слишком близко. */
export class ZombieSystem {
  private active = false;
  private readonly tmpDirection = new THREE.Vector3();
  private readonly tmpStep = new THREE.Vector3();
  private readonly tmpNextPos = new THREE.Vector3();
  private readonly tmpPerp = new THREE.Vector3();
  private readonly tmpRayOrigin = new THREE.Vector3();
  private readonly raycaster = new THREE.Raycaster();

  constructor(private readonly sceneManager: SceneManager) {}

  isActive(): boolean {
    return this.active;
  }

  /** Вызывать один раз, когда смена достигает ZOMBIE_APPEARS_AT_SHIFT — дальше зомби
   *  остаётся активным во всех следующих сменах (повторные вызовы — no-op). */
  async activate(playerPosition: THREE.Vector3): Promise<void> {
    if (this.active) return;
    const spawn = this.findSpawnPosition(playerPosition);
    await this.sceneManager.spawnZombie(spawn);
    this.active = true;
  }

  /** Игрок проиграл смену — зомби исчезает (следующая смена снова 1-я, до
   *  ZOMBIE_APPEARS_AT_SHIFT его быть не должно, см. Game.onShiftEnd). */
  deactivate(): void {
    if (!this.active) return;
    this.sceneManager.removeZombie();
    this.active = false;
  }

  /** Двигает зомби к игроку на один кадр и возвращает дистанцию XZ до него (Infinity,
   *  если зомби не активен) — Game.update() сравнивает её с ATTACK_RANGE сам, чтобы
   *  не плодить циклическую зависимость с HealthSystem здесь. */
  update(
    deltaSec: number,
    playerPosition: THREE.Vector3,
    shiftIndex: number,
    collisionCircles: readonly CollisionCircle[] = EMPTY_CIRCLES,
    collisionRects: readonly CollisionRect[] = EMPTY_RECTS,
    collisionMeshes: readonly THREE.Object3D[] = EMPTY_MESHES,
    raycastExcluded: ReadonlySet<THREE.Object3D> = EMPTY_EXCLUDED,
  ): number {
    if (!this.active) return Infinity;
    const zombie = this.sceneManager.getZombiePosition();
    if (!zombie) return Infinity;

    this.tmpDirection.set(playerPosition.x - zombie.x, 0, playerPosition.z - zombie.z);
    const distance = this.tmpDirection.length();
    if (distance < 1e-4) return distance;
    this.tmpDirection.normalize();

    const speed = this.speedForShift(shiftIndex);
    this.sceneManager.setZombieAnimationSpeed(speed / BASE_SPEED);

    this.tmpStep.copy(this.tmpDirection).multiplyScalar(speed * deltaSec);
    const next = this.moveWithCollision(
      zombie,
      this.tmpStep,
      collisionCircles,
      collisionRects,
      collisionMeshes,
      raycastExcluded,
    );

    const yaw = Math.atan2(this.tmpDirection.x, this.tmpDirection.z);
    this.sceneManager.setZombiePose(next, yaw);
    return distance;
  }

  isWithinAttackRange(distance: number): boolean {
    return distance <= ATTACK_RANGE;
  }

  getDamagePerSecond(): number {
    return DAMAGE_PER_SECOND;
  }

  private speedForShift(shiftIndex: number): number {
    const shiftsSinceAppeared = Math.max(0, shiftIndex - ZOMBIE_APPEARS_AT_SHIFT);
    return Math.min(SPEED_CAP, BASE_SPEED + SPEED_PER_SHIFT * shiftsSinceAppeared);
  }

  /** Точка на SPAWN_DISTANCE от игрока в случайном направлении — пробует несколько
   *  углов и выбирает первый, не попавший в надгробие/забор; если все попытки
   *  неудачны (переполненная сценой зона), просто использует последнюю — не должно
   *  блокировать появление зомби насовсем. */
  private findSpawnPosition(playerPosition: THREE.Vector3): Vec3 {
    const circles = this.sceneManager.getCollisionCircles();
    const rects = this.sceneManager.getCollisionRects();

    let candidate: Vec3 = {
      x: playerPosition.x + SPAWN_DISTANCE,
      y: playerPosition.y - 1.6,
      z: playerPosition.z,
    };
    for (let i = 0; i < SPAWN_ATTEMPTS; i++) {
      const angle = Math.random() * Math.PI * 2;
      const x = playerPosition.x + Math.cos(angle) * SPAWN_DISTANCE;
      const z = playerPosition.z + Math.sin(angle) * SPAWN_DISTANCE;
      candidate = { x, y: playerPosition.y - 1.6, z };
      if (!isPositionBlocked(x, z, ZOMBIE_RADIUS, circles, rects)) break;
    }
    return candidate;
  }

  /** Тот же приём, что у PlayerController.moveWithCollision — двигает по осям
   *  раздельно (X, потом Z), чтобы движение вдоль стены/надгробия не залипало
   *  полностью, когда один из компонентов шага всё ещё разрешён. Без прыжка/vault —
   *  зомби не прыгает, поэтому все круги (включая vaultable) всегда блокируют. */
  private moveWithCollision(
    from: Vec3,
    step: THREE.Vector3,
    circles: readonly CollisionCircle[],
    rects: readonly CollisionRect[],
    meshes: readonly THREE.Object3D[],
    raycastExcluded: ReadonlySet<THREE.Object3D>,
  ): Vec3 {
    const next = { x: from.x, y: from.y, z: from.z };

    this.tmpStep.set(step.x, 0, 0);
    if (!this.isBlocked(next, this.tmpStep, circles, rects, meshes, raycastExcluded)) next.x += step.x;

    this.tmpStep.set(0, 0, step.z);
    if (!this.isBlocked(next, this.tmpStep, circles, rects, meshes, raycastExcluded)) next.z += step.z;

    return next;
  }

  private isBlocked(
    from: Vec3,
    step: THREE.Vector3,
    circles: readonly CollisionCircle[],
    rects: readonly CollisionRect[],
    meshes: readonly THREE.Object3D[],
    raycastExcluded: ReadonlySet<THREE.Object3D>,
  ): boolean {
    if (step.x === 0 && step.z === 0) return false;

    this.tmpNextPos.set(from.x + step.x, from.y, from.z + step.z);
    if (isPositionBlocked(this.tmpNextPos.x, this.tmpNextPos.z, ZOMBIE_RADIUS, circles, rects)) return true;

    if (meshes.length === 0) return false;

    const stepLength = step.length();
    const direction = this.tmpDirection.copy(step).normalize();
    this.raycaster.far = stepLength + ZOMBIE_RADIUS;

    // Тот же трюк, что у игрока: луч по центру плюс слева/справа на ширину радиуса,
    // чтобы не пропускать тонкие стволы/столбы чуть в стороне от линии движения.
    this.tmpPerp.set(-direction.z, 0, direction.x).multiplyScalar(ZOMBIE_RADIUS);

    for (const height of [HIGH_RAY_HEIGHT, LOW_RAY_HEIGHT]) {
      for (const sign of [0, 1, -1]) {
        this.tmpRayOrigin.set(from.x, from.y + height, from.z);
        if (sign !== 0) this.tmpRayOrigin.addScaledVector(this.tmpPerp, sign);
        this.raycaster.set(this.tmpRayOrigin, direction);
        const hits = this.raycaster.intersectObjects(meshes as THREE.Object3D[], true);
        if (hits.some((hit) => !raycastExcluded.has(hit.object))) return true;
      }
    }

    return false;
  }
}
