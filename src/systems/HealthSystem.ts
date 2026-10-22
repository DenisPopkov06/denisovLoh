const MAX_HEALTH = 100;

/** Жизни игрока — тает, пока зомби слишком близко (см. ZombieSystem/Game.update()),
 *  тем же паттерном "процент-ресурс", что и StaminaSystem/FlashlightSystem. В отличие
 *  от них не восстанавливается сама по себе — только полный сброс в начале смены
 *  (Game.startShift), иначе игрок мог бы просто отойти от зомби на секунду и снова
 *  стать неуязвимым, что убивало бы напряжение погони. */
export class HealthSystem {
  private health = MAX_HEALTH;
  /** Навык "Здоровье": полоска по-прежнему в процентах, но урон делится на множитель —
   *  то же самое, что больший запас жизней. */
  private maxHealthMultiplier = 1;

  setMaxHealthMultiplier(multiplier: number): void {
    this.maxHealthMultiplier = Math.max(0.01, multiplier);
  }

  reset(): void {
    this.health = MAX_HEALTH;
  }

  /** amountPerSecond — скорость урона, пока источник урона (зомби) действует;
   *  вызывать каждый кадр с 0, когда урона в этот кадр нет. */
  damage(amountPerSecond: number, deltaSec: number): void {
    if (amountPerSecond <= 0) return;
    this.health = Math.max(0, this.health - (amountPerSecond / this.maxHealthMultiplier) * deltaSec);
  }

  /** Бинты/аптечка (InventorySystem) — мгновенно поднимают здоровье, не выше максимума. */
  heal(amountPercent: number): void {
    this.health = Math.min(MAX_HEALTH, this.health + amountPercent);
  }

  getHealthPercent(): number {
    return this.health;
  }

  isDead(): boolean {
    return this.health <= 0;
  }
}
