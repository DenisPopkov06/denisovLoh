import * as THREE from "three";

// Смещение фонаря относительно глаз (м): в правой руке, чуть ниже.
const FLASHLIGHT_HAND_OFFSET = { x: 0.15, y: -0.2 };
// На каком расстоянии по линии взгляда центр луча сходится с прицелом.
const FLASHLIGHT_AIM_DISTANCE = 20;
// Срок службы лампы (предмет "Запасной фонарик", InventorySystem) — отдельный от
// заряда (chargePercent) ресурс: тает только пока фонарик включён, не восстанавливается
// подзарядом, и не связан с навыком "Фонарь" (тот лишь замедляет расход chargePercent).
// Перегоревшую лампу чинит только покупка нового фонарика — см. Game.update().
const INITIAL_BULB_SECONDS = 240;

export class FlashlightSystem {
  readonly light: THREE.SpotLight;
  private readonly target = new THREE.Object3D();
  private chargePercent = 100;
  private on = false;
  /** Навык "Фонарь": во сколько раз дольше держится заряд (расход делится на него). */
  private durationMultiplier = 1;
  private bulbSecondsLeft = INITIAL_BULB_SECONDS;
  private bulbBurnedOut = false;

  constructor(
    private readonly drainPerSecond = 2,
    private readonly rechargePerSecond = 1,
  ) {
    this.light = new THREE.SpotLight(0xfff2cc, 80, 25, Math.PI / 7, 0.4);
    this.light.decay = 1.2;
    this.light.visible = false;
    // У SpotLight позиция по умолчанию (0, 1, 0) — на метр выше глаз; с целью в
    // метре перед камерой луч уходил под 45° вниз, под ноги. Ставим фонарь у руки
    // (чуть правее и ниже глаз), а цель — далеко по линии взгляда.
    this.light.position.set(FLASHLIGHT_HAND_OFFSET.x, FLASHLIGHT_HAND_OFFSET.y, 0);
    this.target.position.set(0, 0, -FLASHLIGHT_AIM_DISTANCE);
    this.light.target = this.target;

    this.light.castShadow = true;
    this.light.shadow.mapSize.set(512, 512);
    this.light.shadow.camera.near = 0.5;
    this.light.shadow.camera.far = 25;
    this.light.shadow.bias = -0.003;
  }

  setDurationMultiplier(multiplier: number): void {
    this.durationMultiplier = Math.max(0.01, multiplier);
  }

  /** Привязывает фонарик к камере игрока: конус светит туда, куда смотрит камера. */
  attachToCamera(camera: THREE.Camera): void {
    camera.add(this.light);
    camera.add(this.target);
  }

  toggle(): void {
    if (this.bulbBurnedOut) return;
    if (!this.on && this.chargePercent <= 0) return;
    this.on = !this.on;
    this.light.visible = this.on;
  }

  /** Включён — расходует заряд; выключен — медленно восстанавливает (раздел 8 ТЗ:
   *  "можно либо экономить... либо искать батарейки" — подзаряд не отменяет смысл
   *  экономии, т.к. вдвое медленнее расхода). */
  update(deltaSec: number): void {
    if (this.on) {
      this.chargePercent = Math.max(0, this.chargePercent - (this.drainPerSecond / this.durationMultiplier) * deltaSec);
      this.bulbSecondsLeft = Math.max(0, this.bulbSecondsLeft - deltaSec);
      if (this.chargePercent === 0 || this.bulbSecondsLeft === 0) {
        this.on = false;
        this.light.visible = false;
        if (this.bulbSecondsLeft === 0) this.bulbBurnedOut = true;
      }
    } else {
      this.chargePercent = Math.min(100, this.chargePercent + this.rechargePerSecond * deltaSec);
    }
  }

  getChargePercent(): number {
    return this.chargePercent;
  }

  isOn(): boolean {
    return this.on;
  }

  isBulbBurnedOut(): boolean {
    return this.bulbBurnedOut;
  }

  /** Предмет "Запасной фонарик" (InventorySystem) — вставляет лампу с заданным
   *  запасом свечения в секундах и сразу снимает "перегорела". */
  installBulb(seconds: number): void {
    this.bulbSecondsLeft = Math.max(0, seconds);
    this.bulbBurnedOut = this.bulbSecondsLeft <= 0;
  }
}
