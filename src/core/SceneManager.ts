import * as THREE from "three";
import { clone as cloneSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";
import { ObjectState, type ZoneLayout, type PlacedObject, type Vec3 } from "@/data/types";
import { OBJECTS_CATALOG } from "@/data/objects.catalog";
import { AssetLoader } from "@/core/AssetLoader";
import { ObjectStateMachine } from "@/systems/ObjectStateMachine";
import {
  ambientIntensityForShift,
  createAmbientFill,
  createMoonLight,
  createSceneFog,
  localLightFactorForShift,
  moonIntensityForShift,
  skyBackgroundIntensityForShift,
} from "@/render/Lighting";
import { createPlaceholderGround } from "@/render/MaterialsLib";

const FALLEN_TILT_RADIANS = Math.PI / 2;
const DISPLACED_OFFSET_RADIUS = 1.2;

/** Анимированный зомби (риг с клипами walk/attack/death, исходник —
 *  assets_src/blender/zombie_rigged.blend). Отдельно от OBJECTS_CATALOG: это не
 *  декор раскладки, а актёр ZombieSystem со своим набором клипов. */
const ZOMBIE_MODEL_PATH = "models/characters/zombie_walker_rigged.glb";
/** Шаг в клипе ходьбы — короткое шарканье, рассчитанное на медленное движение;
 *  на игровой скорости ZombieSystem (BASE_SPEED) ноги без ускорения заметно не
 *  успевают за перемещением. Множитель подобран так, чтобы шаги совпадали с ним. */
const ZOMBIE_WALK_CLIP_TIME_SCALE = 1.6;
const ZOMBIE_ANIMATION_FADE_SEC = 0.25;

/** Дверь дома смотрителя в zone_*.glb — рядом с ней по E открывается магазин. */
const SHOP_DOOR_NODE = "house_door_a";

export type ZombieAnimation = "walk" | "attack" | "death";
const ZOMBIE_ANIMATIONS: readonly ZombieAnimation[] = ["walk", "attack", "death"];

export interface CollisionCircle {
  x: number;
  z: number;
  radius: number;
  /** Невысокое препятствие — прыжком (см. PlayerController) можно перепрыгнуть через
   *  него; для обычной ходьбы по-прежнему блокирует. */
  vaultable: boolean;
  /** Только для vaultable: true — простым прыжком с места не перепрыгнуть, только
   *  прыжком с разбега (спринт зажат в момент толчка): скамья, крупные валуны —
   *  слишком широкие, обычного прыжка не хватает перелететь целиком. */
  vaultRequiresSprint?: boolean;
}

/** Прямоугольник-коллайдер (всегда сплошная стена, не vaultable) — для длинных прямых
 *  препятствий вроде ограды, которым не подходит ни круг (сильно вытянутый прямоугольник
 *  вместо круга накрыл бы весь двор), ни луч (см. FENCE_MESH_NAME_PATTERN ниже). */
export interface CollisionRect {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

/** objectId -> состояние -> objectId модели-варианта, которую показать вместо базовой
 *  (разрушенные/наклонённые надгробия по арт-листу дизайнера, см. objects.catalog.ts).
 *  Для комбинаций без варианта (например, DISPLACED у gravestone_slab_a — наклонённого
 *  варианта плиты пока нет) используется запасной геометрический сдвиг/поворот. */
const VARIANT_MODEL_BY_STATE: Partial<Record<string, Partial<Record<ObjectState, string>>>> = {
  gravestone_cross_a: {
    [ObjectState.BROKEN]: "gravestone_cross_broken_a",
    [ObjectState.FALLEN]: "gravestone_cross_broken_a",
    [ObjectState.DISPLACED]: "gravestone_cross_tilted_a",
  },
  gravestone_arch_a: {
    [ObjectState.BROKEN]: "gravestone_arch_broken_a",
    [ObjectState.FALLEN]: "gravestone_arch_broken_a",
    [ObjectState.DISPLACED]: "gravestone_arch_tilted_a",
  },
  gravestone_slab_a: {
    [ObjectState.BROKEN]: "gravestone_slab_broken_a",
    [ObjectState.FALLEN]: "gravestone_slab_broken_a",
  },
};

/** Для cross/arch/slab FALLEN показывает ту же "расколотую" модель, что и BROKEN
 *  (отдельного визуала "упавшего, но целого" надгrobия пока нет, см. комментарий
 *  выше) — значит, по факту это одно и то же состояние на экране и должно требовать
 *  того же ремонта (удержание E, "почините"), а не мгновенного "поправить" как у
 *  просто сдвинутого (DISPLACED) надгробия. У переносимых предметов (венки) FALLEN
 *  выглядит иначе (запасной наклон, не "расколото") — для них это не относится. */
function fallenLooksBroken(baseObjectId: string): boolean {
  const variants = VARIANT_MODEL_BY_STATE[baseObjectId];
  const fallenVariant = variants?.[ObjectState.FALLEN];
  return fallenVariant !== undefined && fallenVariant === variants?.[ObjectState.BROKEN];
}

// Подвесной фонарь (lantern_iron_a): origin — точка подвеса, плафон висит на 0.68м ниже
// (комментарий дизайнера в каталоге); у отдельной модели, в отличие от запечённой в зону,
// нет своего источника света в .glb — добавляем его сами.
const LANTERN_OBJECT_ID = "lantern_iron_a";
const LANTERN_HANG_OFFSET_Y = -0.68;

// Статическая геометрия зоны — один слитый меш без отдельных PlacedObject, поэтому
// коллизия для этих именованных "крупных" деталей внутри нет считается по кругу,
// построенному из реального bounding box (по имени меша из Blender). Луч здесь не
// годится универсально — например, у скамьи тонкие ножки, луч на любой высоте может
// пройти между ними, хотя по силуэту она сплошная (та же причина, по которой сквозь
// крупный валун можно было пройти: приплюснутая икосфера невысокая, оба уровня луча
// иногда проходят мимо). rocks_a сюда не входит — это один слитый меш рассыпанной
// по всей зоне гальки (несколько кластеров по 1 крупному + 2-3 мелких валуна,
// assets_src/blender/zone_lib.py build_rocks) — единый bounding box для него был бы
// в размер всей зоны. Вместо этого для rocks_* считаем круг отдельно на каждый
// "остров" геометрии (физически не соприкасающиеся валуны не делят вершины, см.
// computeIslandCircles) и оставляем только острова крупнее ROCK_MIN_COLLISION_RADIUS —
// мелкую гальку (r 0.14-0.34) можно спокойно перешагнуть, блокировать её не нужно.
// tree_ намеренно не здесь: ствол дерева и так надёжно ловится лучом (проходит через
// обе высоты), а bounding box дерева считается по всей кроне — круг получился бы
// в разы шире реального ствола и сделал бы непроходимой зону, где физически пройти
// можно (под кроной, в стороне от ствола).
// vaultable: true — можно перепрыгнуть; vaultRequiresSprint — только прыжком с
// разбега (бочки/ящики — обычным прыжком с места тоже, они невысокие и неширокие;
// скамья — широкая и длинная, обычного прыжка не хватает её перелететь целиком).
// Фонарный столб и постамент остаются сплошной стеной в любом случае.
const STATIC_CIRCLE_NAME_PATTERNS: { pattern: RegExp; vaultable: boolean; vaultRequiresSprint?: boolean }[] = [
  { pattern: /^lamp_post_/, vaultable: false },
  { pattern: /^barrels?_/, vaultable: true },
  { pattern: /^crates?_/, vaultable: true },
  { pattern: /^bench_wood/, vaultable: true, vaultRequiresSprint: true },
  { pattern: /^pedestal_/, vaultable: false },
];
// Ограда (fence_wood_0N, assets_src/blender/zone_lib.py build_fence) — цельный прямой
// забор по всей стороне зоны, круг под него не подходит (накрыл бы собой весь двор).
// Раньше ловилась лучом по staticGeometry наравне с остальной геометрией зоны, но лучи
// идут только на двух строго
// фиксированных высотах (глаза ~1.6м и низкий ~0.5м — см. PlayerController), а у забора
// верхняя жердь на z≈1.05-1.2м — ниже уровня глаз, и сама по себе тонкая; нижняя жердь
// (z≈0.55м) с вероятностью 5% вообще "выпала" (визуальная деталь художника). На стыке
// этих условий луч на любой высоте иногда проходил мимо всей ограды — через один пролёт
// можно было пройти, через соседний (где жердь на месте) нет. Прямоугольник по
// bounding box сегмента не зависит ни от высоты лучей, ни от случайного "выпала": всегда
// сплошная стена по всей длине.
const FENCE_MESH_NAME_PATTERN = /^fence_wood_/;
const ROCK_MESH_NAME_PATTERN = /^rocks_/;
const ROCK_MIN_COLLISION_RADIUS = 0.4;
// Валуны радиусом до этого значения — некрупные, обычным прыжком (без спринта)
// перепрыгиваются; крупнее — только с разбега (vaultRequiresSprint). Было 0.55 —
// самый маленький реально встречающийся остров геометрии уже ~0.57м (см.
// assets_src/blender/zone_lib.py build_rocks, крупный камень кластера r 0.55-0.95
// до масштабирования), так что без спринта не перепрыгивался вообще ни один камень.
const ROCK_SPRINT_REQUIRED_ABOVE_RADIUS = 0.7;

function computeBoundingCircle(mesh: THREE.Mesh, vaultable: boolean, vaultRequiresSprint?: boolean): CollisionCircle {
  mesh.geometry.computeBoundingBox();
  const box = mesh.geometry.boundingBox?.clone() ?? new THREE.Box3();
  box.applyMatrix4(mesh.matrixWorld);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  return {
    x: center.x,
    z: center.z,
    radius: Math.max(size.x, size.z) / 2,
    vaultable,
    ...(vaultRequiresSprint !== undefined && { vaultRequiresSprint }),
  };
}

function computeBoundingRect(mesh: THREE.Mesh): CollisionRect {
  mesh.geometry.computeBoundingBox();
  const box = mesh.geometry.boundingBox?.clone() ?? new THREE.Box3();
  box.applyMatrix4(mesh.matrixWorld);
  return { minX: box.min.x, maxX: box.max.x, minZ: box.min.z, maxZ: box.max.z };
}

/** Разбивает один слитый меш на несвязные "острова" геометрии (например, отдельные
 *  валуны в rocks_a, нигде физически не соприкасающиеся друг с другом — значит, не
 *  делят вершины) и считает bounding-круг для каждого острова отдельно, в мировых
 *  координатах. Группировка — по квантованной позиции вершины (а не по индексу),
 *  чтобы одинаково работать и с indexed-, и с non-indexed-геометрией из экспортера. */
function computeIslandCircles(
  mesh: THREE.Mesh,
  minRadius: number,
  vaultable: boolean,
  sprintRequiredAboveRadius?: number,
): CollisionCircle[] {
  const position = mesh.geometry.attributes.position;
  const index = mesh.geometry.index;
  const triangleCount = (index ? index.count : position.count) / 3;
  const vertexIndex = (t: number, corner: number): number =>
    index ? index.getX(t * 3 + corner) : t * 3 + corner;
  const keyOf = (i: number): string =>
    `${Math.round(position.getX(i) * 1000)}_${Math.round(position.getY(i) * 1000)}_${Math.round(position.getZ(i) * 1000)}`;

  const parent = new Map<string, string>();
  const find = (key: string): string => {
    let root = key;
    while (parent.get(root) !== root) root = parent.get(root)!;
    parent.set(key, root);
    return root;
  };
  const union = (a: string, b: string): void => {
    const rootA = find(a);
    const rootB = find(b);
    if (rootA !== rootB) parent.set(rootA, rootB);
  };

  const triangles: [number, number, number][] = [];
  for (let t = 0; t < triangleCount; t++) {
    const triangle: [number, number, number] = [vertexIndex(t, 0), vertexIndex(t, 1), vertexIndex(t, 2)];
    triangles.push(triangle);
    for (const i of triangle) {
      const key = keyOf(i);
      if (!parent.has(key)) parent.set(key, key);
    }
    union(keyOf(triangle[0]), keyOf(triangle[1]));
    union(keyOf(triangle[1]), keyOf(triangle[2]));
  }

  const worldPoint = new THREE.Vector3();
  const boundsByIsland = new Map<string, THREE.Box3>();
  for (const triangle of triangles) {
    for (const i of triangle) {
      const root = find(keyOf(i));
      let box = boundsByIsland.get(root);
      if (!box) {
        box = new THREE.Box3();
        boundsByIsland.set(root, box);
      }
      worldPoint.set(position.getX(i), position.getY(i), position.getZ(i)).applyMatrix4(mesh.matrixWorld);
      box.expandByPoint(worldPoint);
    }
  }

  const circles: CollisionCircle[] = [];
  for (const box of boundsByIsland.values()) {
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const radius = Math.max(size.x, size.z) / 2;
    if (radius >= minRadius) {
      const vaultRequiresSprint = sprintRequiredAboveRadius !== undefined && radius > sprintRequiredAboveRadius;
      circles.push({
        x: center.x,
        z: center.z,
        radius,
        vaultable,
        ...(vaultRequiresSprint && { vaultRequiresSprint }),
      });
    }
  }
  return circles;
}

/** "Надгробие"-категория для рандомизации раскладки — непроходимый ремонтируемый
 *  объект (collisionRadius задан), а не переносимый мелкий предмет вроде горшка
 *  (у pickup() он тоже repairable, но без collisionRadius). Выводится из каталога,
 *  а не захардкожен по именам — новый тип надгробия дизайнера подхватится сам. */
function isGravestoneLikeObjectId(objectId: string): boolean {
  const entry = OBJECTS_CATALOG[objectId];
  return !!entry && entry.repairableStates.length > 0 && entry.collisionRadius !== undefined;
}

type ItemKind = "pot" | "flowers" | "wreath";

function itemKindOf(objectId: string): ItemKind | null {
  if (objectId === "pot_clay_a") return "pot";
  if (objectId.startsWith("flowers_")) return "flowers";
  if (objectId.startsWith("wreath_")) return "wreath";
  return null;
}

// Фиксированный слот каждого вида предмета относительно его надгробия — локальные
// (x, z) в осях камня (x: вправо от грани, z: вперёд по повороту камня), одинаковый
// на любом камне. Венок — вплотную к лицевой грани (как и был задуман изначально,
// см. objects.catalog.ts: "лицом к +Z, стоят на хвостах ленты — прислонить к
// надгробию"); горшок и цветы — по бокам перед камнем, подальше друг от друга и от
// венка, чтобы три предмета на одном надгробии не перекрывали друг друга.
const ITEM_SLOTS: Record<ItemKind, { x: number; z: number }> = {
  wreath: { x: 0, z: 0.14 },
  pot: { x: 0.45, z: 0.25 },
  flowers: { x: -0.45, z: 0.25 },
};

function shuffleInPlace<T>(items: T[]): void {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
}

function disposeObject(root: THREE.Object3D): void {
  root.traverse((node) => {
    if (node instanceof THREE.Mesh) {
      node.geometry.dispose();
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      for (const material of materials) material.dispose();
    }
  });
}

function enableShadows(root: THREE.Object3D): void {
  root.traverse((node) => {
    if (node instanceof THREE.Mesh) {
      node.castShadow = true;
      node.receiveShadow = true;
    }
  });
}

function createLanternLight(): THREE.PointLight {
  const light = new THREE.PointLight(0xffb84d, 10, 8, 1.8);
  light.position.set(0, LANTERN_HANG_OFFSET_Y + 0.12, 0);
  return light;
}

export class SceneManager {
  readonly scene = new THREE.Scene();

  private zoneRoot: THREE.Group | null = null;
  private staticGeometry: THREE.Object3D | null = null;
  private currentZoneId: string | null = null;
  private currentLayout: ZoneLayout | null = null;
  private readonly interactableObjects: THREE.Object3D[] = [];
  private readonly objectsById = new Map<string, THREE.Object3D>();
  /** Исходный objectId из layout.json — в отличие от userData.objectId на самом
   *  инстансе, не меняется при подмене модели на разрушенный/наклонённый вариант. */
  private readonly baseObjectIdByInstance = new Map<string, string>();
  /** Какая модель должна стоять на инстансе по ПОСЛЕДНЕМУ состоянию. Обновляется сразу
   *  (до загрузки модели), в отличие от userData.objectId, который отстаёт на время
   *  загрузки: без этого быстрая смена состояний (BROKEN → NORMAL → FALLEN, как в
   *  ShiftManager.startShift) оставляла на экране модель от не последнего состояния —
   *  например, сломанное надгробие в состоянии NORMAL, с которым ничего нельзя сделать. */
  private readonly desiredModelByInstance = new Map<string, string>();
  private readonly animationMixers = new Map<THREE.Object3D, THREE.AnimationMixer>();
  private readonly staticCollisionCircles: CollisionCircle[] = [];
  private readonly staticCollisionRects: CollisionRect[] = [];
  /** Меши из staticGeometry, у которых уже есть свой круг-коллайдер (бочки/ящики/
   *  скамья/валуны) — исключаются из лучевой проверки (getStaticCollisionMeshes
   *  всегда включает staticGeometry целиком), иначе луч по этому же мешу ловит их
   *  независимо от прыжка и сводит на нет vaultable/vaultRequiresSprint: круг
   *  разрешает перепрыгнуть, а луч по той же геометрии тут же блокирует снова. */
  private readonly circleCoveredMeshes = new Set<THREE.Object3D>();
  /** Горшок/цветы/венок → надгробие, у которого он стоит (ближайшее на момент загрузки
   *  зоны, из АВТОРСКОЙ раскладки до любых перемешиваний). Надгробия перемешиваются
   *  между собой каждую смену (reshufflePlacedObjects); эти мелкие предметы раньше
   *  либо оставались на СТАРОМ слоте (венки) — после перемешивания там мог оказаться
   *  совсем другой камень (уже/шире исходного), венок либо проваливался внутрь, либо
   *  зависал с зазором, — либо перемешивались отдельной группой МЕЖДУ СОБОЙ (горшки,
   *  цветы), из-за чего у каждого камня предметы вставали как попало (сбоку, спереди,
   *  сзади — какой угодно оригинальный оффсет достался камню по жребию). Теперь у
   *  каждого вида предмета ОДИН фиксированный слот относительно камня (ITEM_SLOTS) —
   *  одинаковый на любом надгrobии, целом или нет, и любом его положении после
   *  перемешивания (repositionPairedItems). DISPLACED по-прежнему сдвигает предмет в
   *  сторону от этого слота (applyFallbackTransform) — так разница "на месте/сдвинуто"
   *  остаётся понятной. */
  private readonly itemAnchors = new Map<string, { gravestoneInstanceId: string; kind: ItemKind }>();
  /** Ссылки нужны, чтобы менять яркость по ходу смен (applyShiftDarkness) —
   *  createAmbientFill()/createMoonLight() добавляются в сцену один раз насовсем,
   *  зона потом грузится/выгружается поверх, без пересоздания света. */
  private readonly ambientLight = createAmbientFill();
  private readonly moonLight = createMoonLight();
  /** Точечные/направленные светильники зоны — запечённые в zone_*.glb (фонарь на
   *  столбе, окна/лампа дома) плюс те, что код добавляет сам на размещённые объекты
   *  (createLanternLight() на lantern_iron_a) — в отличие от ambientLight/moonLight,
   *  это не глобальный свет, а локальные источники, но они точно так же должны
   *  гаснуть по ходу смен (applyShiftDarkness), иначе двор у дома/фонаря остаётся
   *  ярко освещённым независимо от общего затемнения (см. localLightFactorForShift). */
  private readonly zoneLights: { light: THREE.Light; baseIntensity: number }[] = [];
  /** Зомби (ZombieSystem) — отдельный актёр, не часть layout.objects/задач смены:
   *  появляется не сразу (DifficultyScaler.ZOMBIE_APPEARS_AT_SHIFT), переживает смену
   *  зон (зона грузится один раз за игровую сессию, см. main.ts) и не перемешивается
   *  вместе с надгробиями (reshufflePlacedObjects). */
  private zombieInstance: THREE.Object3D | null = null;
  private readonly zombieActions = new Map<ZombieAnimation, THREE.AnimationAction>();
  private zombieCurrentAnimation: ZombieAnimation | null = null;
  private zombieWalkTimeScale = 1;

  constructor(
    private readonly assetLoader: AssetLoader,
    stateMachine: ObjectStateMachine,
  ) {
    this.scene.add(this.ambientLight, this.moonLight);
    this.scene.fog = createSceneFog();
    this.loadSkyBackground();

    // MISSING сюда не входит — та позиция (spawnPosition) приходит из конкретной
    // задачи смены, а не выводится из одной лишь точки привязки, поэтому её
    // отдельно проставляет Game после ShiftManager.startShift().
    stateMachine.onChange((instanceId, state) => {
      if (state !== ObjectState.MISSING) this.handleStateChange(instanceId, state);
    });
  }

  /** Небо — равноугольная (equirectangular) панорама позади модели зоны. Туман не
   *  затрагивает фон, а купол неба внутри самой модели зоны дизайнер закрасил бы
   *  целиком, поэтому фон задаём отдельно, кодом (по просьбе дизайнера). Текстуру
   *  может ещё не подвезти — как и с моделями, отсутствие файла не должно ронять
   *  игру, просто фон останется чёрным, пока дизайнер не выложит sky_night.jpg. */
  private loadSkyBackground(): void {
    new THREE.TextureLoader().load(
      "textures/sky_night.jpg",
      (sky) => {
        sky.mapping = THREE.EquirectangularReflectionMapping;
        sky.colorSpace = THREE.SRGBColorSpace;
        this.scene.background = sky;
      },
      undefined,
      (error) => console.warn('[SceneManager] не удалось загрузить "textures/sky_night.jpg"', error),
    );
  }

  async loadZone(layout: ZoneLayout): Promise<void> {
    this.unloadCurrentZone();

    const zoneRoot = new THREE.Group();
    zoneRoot.name = `zone:${layout.zoneId}`;

    try {
      const zoneGltf = await this.assetLoader.loadModel(layout.modelPath);
      const zoneScene = zoneGltf.scene.clone(true);
      enableShadows(zoneScene);
      zoneRoot.add(zoneScene);
      this.staticGeometry = zoneScene;
      // GLTFLoader материализует KHR_lights_punctual из зоны как реальные THREE.Light —
      // в их числе запечённый "moon_light" (DirectionalLight, см. zone_lib.py
      // build_moon_light): он без теней и существует в .glb для внешних инструментов/
      // просмотра модели отдельно от игры — игра сама создаёт свой DirectionalLight
      // с тенями (createMoonLight, Lighting.ts) в то же направление. Если оставить
      // оба активными, они складываются — и тогда никакое затемнение второго (через
      // applyShiftDarkness) не притушит общий свет, т.к. первый остаётся на полной
      // яркости всегда. Отключаем запечённый дубликат; PointLight/SpotLight (фонарь
      // на столбе, окна/лампа дома) — настоящие локальные светильники, не дубликаты,
      // их не убираем, а копим в zoneLights, чтобы тоже гасить по ходу смен.
      // Снимаем дубликаты ПОСЛЕ traverse, а не внутри колбэка: Object3D.traverse
      // кэширует длину children перед циклом (см. three.core.js), и removeFromParent()
      // прямо во время обхода сдвигает этот массив — следующий индекс оказывается за
      // пределами уже укороченного массива, и .traverse() падает на undefined.
      const duplicateDirectionalLights: THREE.Light[] = [];
      zoneScene.traverse((node) => {
        if (node instanceof THREE.DirectionalLight) {
          duplicateDirectionalLights.push(node);
          return;
        }
        if (node instanceof THREE.PointLight || node instanceof THREE.SpotLight) {
          this.zoneLights.push({ light: node, baseIntensity: node.intensity });
          return;
        }
        if (!(node instanceof THREE.Mesh)) return;
        const staticMatch = STATIC_CIRCLE_NAME_PATTERNS.find((p) => p.pattern.test(node.name));
        if (FENCE_MESH_NAME_PATTERN.test(node.name)) {
          this.staticCollisionRects.push(computeBoundingRect(node));
          this.circleCoveredMeshes.add(node);
        } else if (staticMatch) {
          this.staticCollisionCircles.push(
            computeBoundingCircle(node, staticMatch.vaultable, staticMatch.vaultRequiresSprint),
          );
          this.circleCoveredMeshes.add(node);
        } else if (ROCK_MESH_NAME_PATTERN.test(node.name)) {
          this.staticCollisionCircles.push(
            ...computeIslandCircles(node, ROCK_MIN_COLLISION_RADIUS, true, ROCK_SPRINT_REQUIRED_ABOVE_RADIUS),
          );
          this.circleCoveredMeshes.add(node);
        }
      });
      for (const light of duplicateDirectionalLights) light.removeFromParent();
    } catch (error) {
      // Контент приходит от дизайнера постепенно — отсутствующая/битая модель зоны
      // не должна ронять весь игровой цикл: оставляем плейсхолдер-землю вместо
      // чёрной пустоты, пока дизайнер не выложит .glb.
      console.warn(`[SceneManager] не удалось загрузить модель зоны "${layout.modelPath}"`, error);
      const placeholder = createPlaceholderGround();
      zoneRoot.add(placeholder);
      this.staticGeometry = placeholder;
    }

    await Promise.all(
      layout.objects.map((placed) => this.spawnPlacedObject(placed, zoneRoot)),
    );

    this.scene.add(zoneRoot);
    this.zoneRoot = zoneRoot;
    this.currentZoneId = layout.zoneId;
    this.currentLayout = layout;
    this.computeItemAnchors(layout.objects);
  }

  private async spawnPlacedObject(placed: PlacedObject, parent: THREE.Group): Promise<void> {
    const catalogEntry = OBJECTS_CATALOG[placed.objectId];
    if (!catalogEntry) {
      console.warn(`[SceneManager] objectId "${placed.objectId}" отсутствует в OBJECTS_CATALOG`);
      return;
    }

    let gltf;
    try {
      gltf = await this.assetLoader.loadModel(catalogEntry.modelPath);
    } catch (error) {
      console.warn(`[SceneManager] не удалось загрузить модель объекта "${placed.objectId}"`, error);
      return;
    }

    const instance = gltf.scene.clone(true);
    enableShadows(instance);
    instance.position.set(placed.position.x, placed.position.y, placed.position.z);
    instance.rotation.y = THREE.MathUtils.degToRad(placed.rotationY);
    instance.userData.instanceId = placed.instanceId;
    instance.userData.objectId = placed.objectId;
    instance.userData.interactable = catalogEntry.interactable;

    if (placed.objectId === LANTERN_OBJECT_ID) {
      const lanternLight = createLanternLight();
      instance.add(lanternLight);
      this.zoneLights.push({ light: lanternLight, baseIntensity: lanternLight.intensity });
    }

    parent.add(instance);
    this.objectsById.set(placed.instanceId, instance);
    this.baseObjectIdByInstance.set(placed.instanceId, placed.objectId);
    this.desiredModelByInstance.set(placed.instanceId, placed.objectId);
    this.startAnimations(instance, gltf.animations);
    if (catalogEntry.interactable) this.interactableObjects.push(instance);
  }

  unloadCurrentZone(): void {
    if (this.zoneRoot) {
      this.scene.remove(this.zoneRoot);
      disposeObject(this.zoneRoot);
    }
    this.zoneRoot = null;
    this.staticGeometry = null;
    this.staticCollisionCircles.length = 0;
    this.staticCollisionRects.length = 0;
    this.circleCoveredMeshes.clear();
    this.itemAnchors.clear();
    this.zoneLights.length = 0;
    this.zombieInstance = null;
    this.interactableObjects.length = 0;
    this.objectsById.clear();
    this.baseObjectIdByInstance.clear();
    this.desiredModelByInstance.clear();
    this.animationMixers.clear();
    this.currentZoneId = null;
    this.currentLayout = null;
    this.traps.clear();
  }

  getObjectByInstanceId(instanceId: string): THREE.Object3D | undefined {
    return this.objectsById.get(instanceId);
  }

  /** Исходный objectId из layout.json — в отличие от текущего userData.objectId на
   *  инстансе, не меняется при подмене модели на разрушенный/наклонённый вариант.
   *  Использовать для подписей/текста (HUD и т.п.), а не для коллизий/моделей. */
  getBaseObjectId(instanceId: string): string | undefined {
    return this.baseObjectIdByInstance.get(instanceId);
  }

  /** См. fallenLooksBroken — нужен InteractionSystem, чтобы решить, какой текст
   *  подсказки и какую механику (мгновенно/удержание) показать для FALLEN. */
  isFallenLikeBroken(instanceId: string): boolean {
    const baseObjectId = this.baseObjectIdByInstance.get(instanceId);
    return baseObjectId !== undefined && fallenLooksBroken(baseObjectId);
  }

  /** Исходное место объекта в раскладке зоны (точка привязки у надгробия/вазы). */
  getAnchorTransform(instanceId: string): { position: Vec3; rotationY: number } | null {
    const placed = this.currentLayout?.objects.find((o) => o.instanceId === instanceId);
    return placed ? { position: placed.position, rotationY: placed.rotationY } : null;
  }

  /** Перемешивает, кто где стоит — отдельно надгробия между собой и переносимые
   *  предметы (горшки и т.п.) между собой (авторские "слоты" дизайнера остаются
   *  теми же самыми местами, без путей/заборов, просто инстансы меняются местами),
   *  чтобы раскладка зоны не была одинаковой каждую смену. Вызывать ДО
   *  getShiftConfig() в начале смены — он сам прочитает уже перемешанный
   *  currentLayout.objects, а обновлённые позиции сразу видны и на сцене. */
  reshufflePlacedObjects(): void {
    if (!this.currentLayout) return;
    this.shuffleGroupPositions(isGravestoneLikeObjectId);
    this.repositionPairedItems();
  }

  /** Постепенное затемнение по сменам (ambientIntensityForShift/moonIntensityForShift —
   *  см. Lighting.ts): к 3-4-й смене фонарик уже не опция, а необходимость, чтобы
   *  что-то разглядеть. Вызывать в начале каждой смены. */
  applyShiftDarkness(shiftIndex: number): void {
    this.ambientLight.intensity = ambientIntensityForShift(shiftIndex);
    this.moonLight.intensity = moonIntensityForShift(shiftIndex);
    const localFactor = localLightFactorForShift(shiftIndex);
    for (const { light, baseIntensity } of this.zoneLights) light.intensity = baseIntensity * localFactor;
    this.scene.backgroundIntensity = skyBackgroundIntensityForShift(shiftIndex);
  }

  private shuffleGroupPositions(matches: (objectId: string) => boolean): void {
    if (!this.currentLayout) return;
    const group = this.currentLayout.objects.filter((o) => matches(o.objectId));
    const slots = group.map((o) => ({ position: o.position, rotationY: o.rotationY }));
    shuffleInPlace(slots);

    group.forEach((placed, i) => {
      placed.position = slots[i].position;
      placed.rotationY = slots[i].rotationY;

      const instance = this.objectsById.get(placed.instanceId);
      if (!instance) return;
      instance.position.set(slots[i].position.x, slots[i].position.y, slots[i].position.z);
      instance.rotation.y = THREE.MathUtils.degToRad(slots[i].rotationY);
    });
  }

  /** Считает для каждого горшка/цветов/венка ближайшее (на момент загрузки, по
   *  авторской раскладке) надгробие — см. itemAnchors. Сам слот (ITEM_SLOTS) не
   *  зависит от того, где именно предмет изначально стоял — только от вида. */
  private computeItemAnchors(objects: readonly PlacedObject[]): void {
    this.itemAnchors.clear();
    const gravestones = objects.filter((o) => isGravestoneLikeObjectId(o.objectId));
    for (const item of objects) {
      const kind = itemKindOf(item.objectId);
      if (!kind) continue;

      let nearest: PlacedObject | null = null;
      let nearestDistSq = Infinity;
      for (const grave of gravestones) {
        const dx = item.position.x - grave.position.x;
        const dz = item.position.z - grave.position.z;
        const distSq = dx * dx + dz * dz;
        if (distSq < nearestDistSq) {
          nearestDistSq = distSq;
          nearest = grave;
        }
      }
      if (!nearest) continue;
      this.itemAnchors.set(item.instanceId, { gravestoneInstanceId: nearest.instanceId, kind });
    }
  }

  /** Ставит каждый горшок/цветы/венок в его фиксированный слот (ITEM_SLOTS) у ЕГО
   *  камня на новой, только что перемешанной позиции (см. itemAnchors) — вызывать
   *  сразу после того, как shuffleGroupPositions(isGravestoneLikeObjectId) расставил
   *  камни по новым местам. Один и тот же слот на любом камне — так у всех целых
   *  надгробий горшок/цветы/венок стоят одинаково, независимо от того, где их
   *  изначально расставил дизайнер и где камень оказался после перемешивания. */
  private repositionPairedItems(): void {
    if (!this.currentLayout) return;
    const byInstanceId = new Map(this.currentLayout.objects.map((o) => [o.instanceId, o]));

    for (const [itemInstanceId, anchor] of this.itemAnchors) {
      const item = byInstanceId.get(itemInstanceId);
      const grave = byInstanceId.get(anchor.gravestoneInstanceId);
      if (!item || !grave) continue;

      const slot = ITEM_SLOTS[anchor.kind];
      const graveRad = THREE.MathUtils.degToRad(grave.rotationY);
      const cos = Math.cos(graveRad);
      const sin = Math.sin(graveRad);
      item.position = {
        x: grave.position.x + slot.x * cos - slot.z * sin,
        y: item.position.y,
        z: grave.position.z + slot.x * sin + slot.z * cos,
      };
      item.rotationY = grave.rotationY;

      const instance = this.objectsById.get(itemInstanceId);
      if (!instance) continue;
      instance.position.set(item.position.x, item.position.y, item.position.z);
      instance.rotation.y = THREE.MathUtils.degToRad(item.rotationY);
    }
  }

  private handleStateChange(instanceId: string, state: ObjectState): void {
    const object = this.objectsById.get(instanceId);
    const baseObjectId = this.baseObjectIdByInstance.get(instanceId);
    if (!object || !baseObjectId) return;

    const variantId = VARIANT_MODEL_BY_STATE[baseObjectId]?.[state];
    const targetModelId = variantId ?? baseObjectId;
    // Запоминаем желаемую модель сразу: устаревшие результаты загрузки (setInstanceModel)
    // сверяются с ней и отбрасываются, так что побеждает всегда последнее состояние.
    this.desiredModelByInstance.set(instanceId, targetModelId);

    if (targetModelId !== object.userData.objectId) {
      // Модель-вариант (разбитая/наклонённая) уже сама выглядит как нужное состояние —
      // ставится точно на точку привязки, без дополнительного геометрического сдвига.
      void this.setInstanceModel(instanceId, targetModelId);
    } else if (!variantId) {
      // Нужная модель уже показана (обычно базовая); для DISPLACED/FALLEN без
      // предусмотренного варианта — запасной геометрический сдвиг/поворот.
      this.applyFallbackTransform(instanceId, state);
    }
  }

  private async setInstanceModel(instanceId: string, modelObjectId: string): Promise<void> {
    const anchor = this.getAnchorTransform(instanceId);
    const baseObjectId = this.baseObjectIdByInstance.get(instanceId);
    if (!anchor || !baseObjectId || !this.zoneRoot) return;

    const catalogEntry = OBJECTS_CATALOG[modelObjectId];
    if (!catalogEntry) return;

    let gltf;
    try {
      gltf = await this.assetLoader.loadModel(catalogEntry.modelPath);
    } catch (error) {
      console.warn(`[SceneManager] не удалось загрузить вариант модели "${modelObjectId}"`, error);
      return;
    }

    // Пока модель грузилась, могло прийти более новое состояние (нужна уже другая модель)
    // или зона выгрузиться — тогда этот устаревший результат подставлять нельзя. Текущий
    // инстанс берём ПОСЛЕ await, а не до: заменять надо то, что стоит на момент подмены.
    if (this.desiredModelByInstance.get(instanceId) !== modelObjectId) return;
    const current = this.objectsById.get(instanceId);
    if (!current || !this.zoneRoot) return;

    const interactable = OBJECTS_CATALOG[baseObjectId]?.interactable ?? false;
    const next = gltf.scene.clone(true);
    enableShadows(next);
    next.position.set(anchor.position.x, anchor.position.y, anchor.position.z);
    next.rotation.y = THREE.MathUtils.degToRad(anchor.rotationY);
    next.userData.instanceId = instanceId;
    next.userData.objectId = modelObjectId;
    next.userData.interactable = interactable;

    this.zoneRoot.add(next);
    this.objectsById.set(instanceId, next);
    this.startAnimations(next, gltf.animations);

    const interactIndex = this.interactableObjects.indexOf(current);
    if (interactIndex !== -1) {
      if (interactable) this.interactableObjects[interactIndex] = next;
      else this.interactableObjects.splice(interactIndex, 1);
    } else if (interactable) {
      this.interactableObjects.push(next);
    }

    this.zoneRoot.remove(current);
    this.stopAnimations(current);
    disposeObject(current);
  }

  /** Запасной визуал для состояний без готовой модели-варианта: FALLEN — завален
   *  набок у своего места (или лёг плашмя — см. fallenLiesFlat); DISPLACED — сдвинут
   *  в сторону от точки привязки; остальное (в первую очередь NORMAL) — ровно на
   *  своём авторском месте. */
  private applyFallbackTransform(instanceId: string, state: ObjectState): void {
    const object = this.objectsById.get(instanceId);
    const anchor = this.getAnchorTransform(instanceId);
    if (!object || !anchor) return;

    const anchorRotationRad = THREE.MathUtils.degToRad(anchor.rotationY);

    if (state === ObjectState.FALLEN) {
      object.position.set(anchor.position.x, anchor.position.y, anchor.position.z);
      object.rotation.set(0, anchorRotationRad, 0);
      const baseObjectId = this.baseObjectIdByInstance.get(instanceId);
      const liesFlat = baseObjectId !== undefined && OBJECTS_CATALOG[baseObjectId]?.fallenLiesFlat;
      if (liesFlat) {
        // NORMAL уже стоит вертикально ("на хвостах ленты", лицом к +Z — см.
        // objects.catalog.ts); рядовой топпл вокруг Z (как у надгробий) оставил бы
        // его вертикальным, просто повёрнутым на ребро — визуально "висит без опоры".
        // Вместо этого кладём плашмя поворотом вокруг X, ВСЕГДА в сторону локального
        // +Z (наружу, от надгробия, к которому он был прислонён), а не в случайную
        // сторону — иначе на -Z он лёг бы прямо в основание камня.
        object.rotateX(FALLEN_TILT_RADIANS);
      } else {
        object.rotateZ(Math.random() < 0.5 ? FALLEN_TILT_RADIANS : -FALLEN_TILT_RADIANS);
      }
      return;
    }

    if (state === ObjectState.DISPLACED) {
      const angle = Math.random() * Math.PI * 2;
      object.position.set(
        anchor.position.x + Math.cos(angle) * DISPLACED_OFFSET_RADIUS,
        anchor.position.y,
        anchor.position.z + Math.sin(angle) * DISPLACED_OFFSET_RADIUS,
      );
      object.rotation.set(0, anchorRotationRad, 0);
      return;
    }

    object.position.set(anchor.position.x, anchor.position.y, anchor.position.z);
    object.rotation.set(0, anchorRotationRad, 0);
  }

  private startAnimations(object: THREE.Object3D, clips: THREE.AnimationClip[]): void {
    if (clips.length === 0) return;
    const mixer = new THREE.AnimationMixer(object);
    for (const clip of clips) mixer.clipAction(clip).play();
    this.animationMixers.set(object, mixer);
  }

  private stopAnimations(object: THREE.Object3D): void {
    this.animationMixers.delete(object);
  }

  /** Тикает AnimationMixer всех заспавненных объектов со своими клипами (например,
   *  взмах крыльев у бабочки) — вызывать каждый кадр из Game.update(). */
  updateAnimations(deltaSec: number): void {
    for (const mixer of this.animationMixers.values()) mixer.update(deltaSec);
  }

  /** Телепортирует уже заспавненный инстанс на новую позицию без смены родителя —
   *  используется, чтобы "уронить в траву" пропавший предмет в начале смены (MISSING). */
  relocateInstance(instanceId: string, position: Vec3): void {
    this.objectsById.get(instanceId)?.position.set(position.x, position.y, position.z);
  }

  /** Возвращает предмет, который игрок нёс в руках, обратно в сцену зоны
   *  (а не в scene напрямую — иначе он пережил бы выгрузку зоны и протёк бы в неё следующую). */
  placeCarriedObject(object: THREE.Object3D, position: Vec3, rotationY: number): void {
    this.zoneRoot?.add(object);
    object.position.set(position.x, position.y, position.z);
    object.rotation.set(0, THREE.MathUtils.degToRad(rotationY), 0);
  }

  getCurrentZoneId(): string | null {
    return this.currentZoneId;
  }

  getCurrentLayout(): ZoneLayout | null {
    return this.currentLayout;
  }

  getInteractableObjects(): THREE.Object3D[] {
    return this.interactableObjects;
  }

  /** Статическая геометрия зоны (дерево/фонари/ограда и т.п., запечённые в модель
   *  зоны дизайнером) плюс расставленные объекты с collisionMesh в каталоге (дом,
   *  ворота, забор, скамья — длинные/с проходом, круг им не подходит) — для коллизии
   *  игрока лучом вперёд по курсу движения. */
  /** Точка у двери дома смотрителя (узел SHOP_DOOR_NODE в запечённой геометрии
   *  зоны) — там открывается магазин. null — в зоне нет дома. */
  getShopAnchor(): Vec3 | null {
    const door = this.staticGeometry?.getObjectByName(SHOP_DOOR_NODE);
    if (!door) return null;
    const center = new THREE.Box3().setFromObject(door).getCenter(new THREE.Vector3());
    return { x: center.x, y: center.y, z: center.z };
  }

  getStaticCollisionMeshes(): THREE.Object3D[] {
    const meshes: THREE.Object3D[] = this.staticGeometry ? [this.staticGeometry] : [];
    for (const object of this.objectsById.values()) {
      const objectId = object.userData.objectId as string | undefined;
      if (objectId && OBJECTS_CATALOG[objectId]?.collisionMesh) meshes.push(object);
    }
    return meshes;
  }

  /** Меши из staticGeometry, уже имеющие свой круг-коллайдер — PlayerController
   *  отбрасывает попадания луча по ним (см. circleCoveredMeshes), чтобы прыжок
   *  с разбега не наталкивался на ту же геометрию через луч в обход vaultable-круга. */
  getRaycastExcludedMeshes(): ReadonlySet<THREE.Object3D> {
    return this.circleCoveredMeshes;
  }

  /** Круги-коллайдеры для расставленных непроходимых объектов (надгробия и т.п.,
   *  у которых в каталоге задан collisionRadius) — считается по их текущей,
   *  а не исходной позиции (DISPLACED/FALLEN/MISSING могут их сдвигать), и по
   *  актуально показанной модели (разбитый вариант может иметь другой радиус). */
  getCollisionCircles(): CollisionCircle[] {
    const circles: CollisionCircle[] = [...this.staticCollisionCircles];
    for (const object of this.objectsById.values()) {
      const objectId = object.userData.objectId as string | undefined;
      const catalogEntry = objectId ? OBJECTS_CATALOG[objectId] : undefined;
      if (!catalogEntry?.collisionRadius) continue;
      circles.push({
        x: object.position.x,
        z: object.position.z,
        radius: catalogEntry.collisionRadius,
        vaultable: catalogEntry.vaultable ?? false,
      });
    }
    return circles;
  }

  /** Прямоугольники-коллайдеры ограды (см. FENCE_MESH_NAME_PATTERN) — считаются один
   *  раз при загрузке зоны, забор не двигается и не меняет состояние. */
  getCollisionRects(): readonly CollisionRect[] {
    return this.staticCollisionRects;
  }

  // --- Зомби (ZombieSystem) ---------------------------------------------------

  /** Спавнит зомби в сцене (не более одного за раз — повторный вызов, пока он уже
   *  есть, игнорируется) и запускает клип ходьбы. Клипы не играют одновременно, как
   *  у декора (startAnimations) — переключаются playZombieAnimation(). */
  async spawnZombie(position: Vec3): Promise<void> {
    if (this.zombieInstance || !this.zoneRoot) return;

    let gltf;
    try {
      gltf = await this.assetLoader.loadModel(ZOMBIE_MODEL_PATH);
    } catch (error) {
      console.warn(`[SceneManager] не удалось загрузить модель зомби "${ZOMBIE_MODEL_PATH}"`, error);
      return;
    }
    // Пока модель грузилась, зона могла выгрузиться или зомби уже успели заспавнить
    // повторным вызовом — тогда этот результат уже не актуален.
    if (this.zombieInstance || !this.zoneRoot) return;

    // SkeletonUtils.clone, а не Object3D.clone: у скиннед-меша обычный clone оставляет
    // ссылку на кости ИСХОДНОЙ (кэшированной загрузчиком) сцены — анимация двигала бы их.
    const instance = cloneSkinned(gltf.scene);
    enableShadows(instance);
    instance.position.set(position.x, position.y, position.z);
    this.zoneRoot.add(instance);
    this.zombieInstance = instance;

    const mixer = new THREE.AnimationMixer(instance);
    for (const name of ZOMBIE_ANIMATIONS) {
      const clip = THREE.AnimationClip.findByName(gltf.animations, name);
      if (!clip) {
        console.warn(`[SceneManager] у модели зомби нет клипа "${name}"`);
        continue;
      }
      const action = mixer.clipAction(clip);
      if (name === "death") {
        // Один раз и остаётся лежать на последнем кадре.
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
      }
      this.zombieActions.set(name, action);
    }
    this.animationMixers.set(instance, mixer);
    this.zombieWalkTimeScale = 1;
    this.playZombieAnimation("walk");
  }

  /** Убирает зомби со сцены (игрок проиграл смену — начинаем заново с 1-й смены,
   *  где зомби ещё не должно быть; см. Game.onShiftEnd). */
  removeZombie(): void {
    if (!this.zombieInstance) return;
    this.stopAnimations(this.zombieInstance);
    this.zombieActions.clear();
    this.zombieCurrentAnimation = null;
    this.zombieInstance.removeFromParent();
    disposeObject(this.zombieInstance);
    this.zombieInstance = null;
  }

  /** Плавно (кроссфейдом) переключает клип зомби; повторный вызов с тем же клипом —
   *  no-op, поэтому ZombieSystem может звать его каждый кадр. */
  playZombieAnimation(name: ZombieAnimation): void {
    if (this.zombieCurrentAnimation === name) return;
    const next = this.zombieActions.get(name);
    if (!next) return;
    const previous = this.zombieCurrentAnimation ? this.zombieActions.get(this.zombieCurrentAnimation) : undefined;
    next.reset();
    next.timeScale = name === "walk" ? ZOMBIE_WALK_CLIP_TIME_SCALE * this.zombieWalkTimeScale : 1;
    next.play();
    if (previous) previous.crossFadeTo(next, ZOMBIE_ANIMATION_FADE_SEC, false);
    this.zombieCurrentAnimation = name;
  }

  isZombieActive(): boolean {
    return this.zombieInstance !== null;
  }

  /** Текущая позиция зомби — ZombieSystem двигает её сам (AI), SceneManager только
   *  хранит актёра и его коллизии/анимацию. */
  getZombiePosition(): Vec3 | null {
    if (!this.zombieInstance) return null;
    const { x, y, z } = this.zombieInstance.position;
    return { x, y, z };
  }

  /** position — новая позиция (XZ двигает ZombieSystem, Y не меняется — зомби ходит
   *  по плоской земле зоны, как и игрок); yawRadians — поворот лицом к направлению
   *  движения (модель смотрит на +Z glTF в нейтральной позе, см. каталог). */
  setZombiePose(position: Vec3, yawRadians: number): void {
    if (!this.zombieInstance) return;
    this.zombieInstance.position.set(position.x, position.y, position.z);
    this.zombieInstance.rotation.y = yawRadians;
  }

  /** Ускоряет/замедляет проигрывание клипа ходьбы вместе со скоростью зомби (иначе
   *  ноги перебирают с одной и той же частотой независимо от того, как быстро он
   *  на самом деле едет по земле — на высоких сменах выглядело бы как скольжение). */
  setZombieAnimationSpeed(timeScale: number): void {
    // Только ходьба: удар и падение — с собственной скоростью, независимо от смены.
    this.zombieWalkTimeScale = timeScale;
    const walk = this.zombieActions.get("walk");
    if (walk) walk.timeScale = ZOMBIE_WALK_CLIP_TIME_SCALE * timeScale;
  }

  // --- Капкан (предмет "Капкан", InventorySystem) -----------------------------
  // Процедурная геометрия (без внешних ассетов — public/models не трогаем): низкая
  // база и две "челюсти"-конуса, тёмный металл. ZombieSystem.stun() вызывается из
  // Game.updateZombie(), когда зомби оказывается достаточно близко к одной из них.

  private readonly traps = new Map<string, THREE.Object3D>();
  private trapCounter = 0;

  /** Ставит капкан у ног игрока и возвращает его id (removeTrap/getActiveTraps). */
  placeTrap(position: Vec3): string {
    const material = new THREE.MeshStandardMaterial({ color: 0x2a2a2e, metalness: 0.75, roughness: 0.35 });
    const group = new THREE.Group();

    const base = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.24, 0.02, 16), material);
    group.add(base);
    for (const side of [-1, 1] as const) {
      const jaw = new THREE.Mesh(new THREE.ConeGeometry(0.045, 0.24, 6), material);
      jaw.position.set(side * 0.1, 0.09, 0);
      jaw.rotation.z = side * (Math.PI / 5);
      group.add(jaw);
    }
    group.position.set(position.x, position.y, position.z);
    group.traverse((node) => {
      if (node instanceof THREE.Mesh) node.castShadow = true;
    });
    this.zoneRoot?.add(group);

    const id = `trap-${this.trapCounter++}`;
    this.traps.set(id, group);
    return id;
  }

  /** Срабатывание (зомби задел капкан) или истёк срок — убирает его со сцены. */
  removeTrap(id: string): void {
    const trap = this.traps.get(id);
    if (!trap) return;
    trap.removeFromParent();
    disposeObject(trap);
    this.traps.delete(id);
  }

  /** Позиции расставленных капканов — ZombieSystem/Game сверяет с ними дистанцию
   *  до зомби каждый кадр, не зная о THREE-объектах капкана вообще. */
  getActiveTraps(): { id: string; x: number; z: number }[] {
    return Array.from(this.traps.entries()).map(([id, group]) => ({ id, x: group.position.x, z: group.position.z }));
  }
}
