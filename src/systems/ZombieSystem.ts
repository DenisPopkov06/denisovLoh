import * as THREE from "three";
import type { Vec3 } from "@/data/types";
import type { SceneManager, CollisionCircle, CollisionRect } from "@/core/SceneManager";
import { ZOMBIE_APPEARS_AT_SHIFT } from "@/systems/DifficultyScaler";
import { GridPathfinder, type Point2 } from "@/systems/ZombiePathfinder";

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
// Выход из удара — с запасом (гистерезис): иначе на самой границе ATTACK_RANGE
// клипы удара/ходьбы дёргались бы туда-обратно каждый кадр.
const ATTACK_EXIT_RANGE = ATTACK_RANGE + 0.35;
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
// Поиск пути (GridPathfinder): клетка сетки, сколько клеток максимум обходить за
// один поиск, как часто пересчитывать путь и насколько игрок должен сместиться,
// чтобы пересчитать сразу, не дожидаясь таймера.
const PATH_CELL = 0.5;
const PATH_MAX_EXPANSIONS = 5000;
const REPLAN_SEC = 0.6;
const REPLAN_PLAYER_MOVED = 1.2;
const WAYPOINT_REACHED = 0.3;
// Почти не сдвинулся за STUCK_SEC при попытке идти — путь устарел (надгробия
// перемешались, упёрся в угол), пересчитываем немедленно.
const STUCK_SEC = 0.6;
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

type ZombieState = "chase" | "attack" | "dead";

/** Зомби (моб-преследователь, появляется с ZOMBIE_APPEARS_AT_SHIFT): идёт к игроку,
 *  обходя ту же коллизию, что и игрок (надгробия, ограда, статическая геометрия зоны),
 *  — если прямая дорога перекрыта, ищет путь в обход (GridPathfinder). Разгоняется со
 *  сменами и отнимает жизни игрока (HealthSystem), если подойти слишком близко. */
export class ZombieSystem {
  private active = false;
  private state: ZombieState = "chase";
  /** Капкан (InventorySystem "trap") — замирает на месте (не идёт, не бьёт) на это
   *  время; в отличие от kill() не меняет state и анимацию ходьбы не трогает, просто
   *  останавливает её (freeze кадра) — читается как "застрял", а не "умер". */
  private stunnedRemainingSec = 0;
  private readonly tmpDirection = new THREE.Vector3();
  private readonly tmpStep = new THREE.Vector3();
  private readonly tmpNextPos = new THREE.Vector3();
  private readonly tmpPerp = new THREE.Vector3();
  private readonly tmpRayOrigin = new THREE.Vector3();
  private readonly raycaster = new THREE.Raycaster();
  private readonly tmpMoveDir = new THREE.Vector3();
  private readonly tmpAxis = new THREE.Vector3();

  private readonly pathfinder = new GridPathfinder(PATH_CELL, PATH_MAX_EXPANSIONS);
  private path: Point2[] = [];
  private replanTimer = 0;
  private lastGoal: Point2 | null = null;
  private stuckTimer = 0;
  /** Занятость клетки статической геометрией (лучи) — она не двигается, поэтому
   *  считается один раз на клетку; круги/ограда проверяются каждый раз заново
   *  (надгробия перемешиваются каждую смену). */
  private readonly meshBlockedCache = new Map<string, boolean>();

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
    this.state = "chase";
    this.stunnedRemainingSec = 0;
    this.resetPath();
  }

  /** Игрок проиграл смену — зомби исчезает (следующая смена снова 1-я, до
   *  ZOMBIE_APPEARS_AT_SHIFT его быть не должно, см. Game.onShiftEnd). */
  deactivate(): void {
    if (!this.active) return;
    this.sceneManager.removeZombie();
    this.active = false;
    this.state = "chase";
    this.stunnedRemainingSec = 0;
    this.resetPath();
    this.meshBlockedCache.clear();
  }

  /** Зомби убит: проигрывает падение и остаётся лежать — больше не ходит и не бьёт
   *  (update() возвращает Infinity). Убрать тело — deactivate(). */
  kill(): void {
    if (!this.active || this.state === "dead") return;
    this.state = "dead";
    this.sceneManager.playZombieAnimation("death");
  }

  isDead(): boolean {
    return this.state === "dead";
  }

  /** Капкан сработал: зомби замирает на stunSec, анимация ходьбы останавливается
   *  (timeScale 0 — не переключаем клип, чтобы не терять текущую фазу шага). */
  stun(stunSec: number): void {
    if (!this.active || this.state === "dead") return;
    this.stunnedRemainingSec = Math.max(this.stunnedRemainingSec, stunSec);
  }

  isStunned(): boolean {
    return this.stunnedRemainingSec > 0;
  }

  /** Двигает зомби к игроку на один кадр и возвращает дистанцию XZ до него (Infinity,
   *  если зомби не активен или убит) — Game.update() сравнивает её с ATTACK_RANGE сам,
   *  чтобы не плодить циклическую зависимость с HealthSystem здесь. Вплотную к игроку
   *  зомби останавливается и бьёт (клип attack), отошёл — снова идёт (walk). */
  update(
    deltaSec: number,
    playerPosition: THREE.Vector3,
    shiftIndex: number,
    collisionCircles: readonly CollisionCircle[] = EMPTY_CIRCLES,
    collisionRects: readonly CollisionRect[] = EMPTY_RECTS,
    collisionMeshes: readonly THREE.Object3D[] = EMPTY_MESHES,
    raycastExcluded: ReadonlySet<THREE.Object3D> = EMPTY_EXCLUDED,
  ): number {
    if (!this.active || this.state === "dead") return Infinity;
    const zombie = this.sceneManager.getZombiePosition();
    if (!zombie) return Infinity;

    this.tmpDirection.set(playerPosition.x - zombie.x, 0, playerPosition.z - zombie.z);
    const distance = this.tmpDirection.length();
    if (distance < 1e-4) return distance;
    this.tmpDirection.normalize();
    const yaw = Math.atan2(this.tmpDirection.x, this.tmpDirection.z);

    if (this.stunnedRemainingSec > 0) {
      this.stunnedRemainingSec = Math.max(0, this.stunnedRemainingSec - deltaSec);
      this.sceneManager.setZombieAnimationSpeed(0);
      return distance;
    }

    if (this.state === "chase" && distance <= ATTACK_RANGE) this.state = "attack";
    else if (this.state === "attack" && distance > ATTACK_EXIT_RANGE) this.state = "chase";

    if (this.state === "attack") {
      // Стоит на месте и бьёт, всё время развернувшись к игроку.
      this.sceneManager.playZombieAnimation("attack");
      this.sceneManager.setZombiePose(zombie, yaw);
      return distance;
    }

    this.sceneManager.playZombieAnimation("walk");
    const speed = this.speedForShift(shiftIndex);
    this.sceneManager.setZombieAnimationSpeed(speed / BASE_SPEED);

    const isBlocked = (x: number, z: number): boolean =>
      isPositionBlocked(x, z, ZOMBIE_RADIUS, collisionCircles, collisionRects) ||
      this.isMeshBlockedAt(x, z, zombie.y, collisionMeshes, raycastExcluded);
    const target = this.nextWaypoint(deltaSec, zombie, playerPosition, isBlocked);
    this.tmpMoveDir.set(target.x - zombie.x, 0, target.z - zombie.z);
    if (this.tmpMoveDir.lengthSq() < 1e-8) this.tmpMoveDir.copy(this.tmpDirection);
    this.tmpMoveDir.normalize();

    this.tmpStep.copy(this.tmpMoveDir).multiplyScalar(speed * deltaSec);
    const next = this.moveWithCollision(
      zombie,
      this.tmpStep,
      collisionCircles,
      collisionRects,
      collisionMeshes,
      raycastExcluded,
    );

    const moved = Math.hypot(next.x - zombie.x, next.z - zombie.z);
    this.stuckTimer = moved < speed * deltaSec * 0.25 ? this.stuckTimer + deltaSec : 0;
    if (this.stuckTimer >= STUCK_SEC) {
      this.stuckTimer = 0;
      this.path = [];
      this.replanTimer = 0;
    }

    this.sceneManager.setZombiePose(next, Math.atan2(this.tmpMoveDir.x, this.tmpMoveDir.z));
    return distance;
  }

  /** Куда идти в этом кадре: прямо к игроку, если дорога свободна, иначе — к
   *  следующей точке найденного обходного пути (пересчитывается по таймеру, когда
   *  игрок заметно сместился, или если зомби застрял). Пути нет совсем (игрок
   *  недостижим) — идёт напрямую, как раньше. */
  private nextWaypoint(
    deltaSec: number,
    zombie: Vec3,
    player: THREE.Vector3,
    isBlocked: (x: number, z: number) => boolean,
  ): Point2 {
    const from = { x: zombie.x, z: zombie.z };
    const goal = { x: player.x, z: player.z };
    this.replanTimer -= deltaSec;
    const goalMoved =
      !this.lastGoal || Math.hypot(goal.x - this.lastGoal.x, goal.z - this.lastGoal.z) > REPLAN_PLAYER_MOVED;
    if (this.replanTimer <= 0 || goalMoved || this.path.length === 0) {
      this.replanTimer = REPLAN_SEC;
      this.lastGoal = goal;
      this.path = this.pathfinder.isSegmentClear(from, goal, isBlocked)
        ? [goal]
        : (this.pathfinder.findPath(from, goal, isBlocked) ?? [goal]);
    }
    // Последняя точка пути — сам игрок: держим её актуальной между пересчётами.
    this.path[this.path.length - 1] = goal;
    while (this.path.length > 1 && Math.hypot(this.path[0].x - from.x, this.path[0].z - from.z) < WAYPOINT_REACHED) {
      this.path.shift();
    }
    return this.path[0] ?? goal;
  }

  private isMeshBlockedAt(
    x: number,
    z: number,
    groundY: number,
    meshes: readonly THREE.Object3D[],
    raycastExcluded: ReadonlySet<THREE.Object3D>,
  ): boolean {
    if (meshes.length === 0) return false;
    const key = `${x.toFixed(2)},${z.toFixed(2)}`;
    const cached = this.meshBlockedCache.get(key);
    if (cached !== undefined) return cached;

    // Два луча крест-накрест через клетку (вдоль X и вдоль Z) длиной в диаметр
    // зомби, на тех же двух высотах, что и при движении (isBlocked).
    let blocked = false;
    this.raycaster.far = ZOMBIE_RADIUS * 2;
    for (const height of [HIGH_RAY_HEIGHT, LOW_RAY_HEIGHT]) {
      for (const [ax, az] of [
        [1, 0],
        [0, 1],
      ] as const) {
        this.tmpAxis.set(ax, 0, az);
        this.tmpRayOrigin.set(x - ax * ZOMBIE_RADIUS, groundY + height, z - az * ZOMBIE_RADIUS);
        this.raycaster.set(this.tmpRayOrigin, this.tmpAxis);
        const hits = this.raycaster.intersectObjects(meshes as THREE.Object3D[], true);
        if (hits.some((hit) => !raycastExcluded.has(hit.object))) {
          blocked = true;
          break;
        }
      }
      if (blocked) break;
    }
    this.meshBlockedCache.set(key, blocked);
    return blocked;
  }

  private resetPath(): void {
    this.path = [];
    this.replanTimer = 0;
    this.lastGoal = null;
    this.stuckTimer = 0;
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
    // step может быть тем же this.tmpStep, который ниже переиспользуется под шаг по
    // одной оси, — компоненты нужно запомнить до этого, иначе Z обнулялся раньше,
    // чем его успевали применить, и зомби ходил только вдоль X.
    const stepX = step.x;
    const stepZ = step.z;

    this.tmpStep.set(stepX, 0, 0);
    if (!this.isBlocked(next, this.tmpStep, circles, rects, meshes, raycastExcluded)) next.x += stepX;

    this.tmpStep.set(0, 0, stepZ);
    if (!this.isBlocked(next, this.tmpStep, circles, rects, meshes, raycastExcluded)) next.z += stepZ;

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
