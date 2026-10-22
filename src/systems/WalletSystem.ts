/** Награда за каждую выполненную задачу смены и бонус за закрытую целиком смену
 *  (растёт со сменами — дальше задачи сложнее, а прокачка дороже). */
export const TASK_REWARD = 75;
export const SHIFT_BONUS_BASE = 150;
export const SHIFT_BONUS_PER_SHIFT = 25;

export function shiftCompletionBonus(shiftIndex: number): number {
  return SHIFT_BONUS_BASE + SHIFT_BONUS_PER_SHIFT * Math.max(0, shiftIndex - 1);
}

/** Монеты игрока — тратятся в магазине у дома (ShopScreen), копятся между сменами
 *  и сохраняются (SaveData.coins). */
export class WalletSystem {
  private coins = 0;

  load(coins: number | undefined): void {
    this.coins = typeof coins === "number" && Number.isFinite(coins) ? Math.max(0, Math.floor(coins)) : 0;
  }

  getCoins(): number {
    return this.coins;
  }

  add(amount: number): void {
    if (amount > 0) this.coins += Math.floor(amount);
  }

  /** Списывает, только если хватает; false — денег мало, баланс не меняется. */
  trySpend(amount: number): boolean {
    if (amount < 0 || amount > this.coins) return false;
    this.coins -= amount;
    return true;
  }
}
