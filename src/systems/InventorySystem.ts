/** Предметы магазина (ShopScreen, правая панель): в отличие от навыков (SkillSystem,
 *  вечный множитель) каждый предмет — расходуемый запас ("remaining"), который тает
 *  от использования и рано или поздно кончается — тогда эффект пропадает, пока не
 *  купишь снова. Это и есть "срок использования": для патронов/лопаты/лампочки
 *  remaining считает заряды/использования, для бинтов/аптечки/капкана — штуки.
 *  Повторная покупка одного и того же предмета дороже предыдущей (rebuyGrowth,
 *  до growthCap) — чем дальше по сменам, тем выше цена "просто остаться на плаву",
 *  это и создаёт нарастающую сложность без изменения урона/времени смены. */
export type ItemId = "shovel" | "pistol" | "flashlightItem" | "medkit" | "crowbar" | "ammo" | "bandage" | "key" | "trap";

export type ItemCategory = "weapon" | "tool" | "consumable" | "special";

export interface ItemDefinition {
  id: ItemId;
  title: string;
  description: string;
  category: ItemCategory;
  /** Единица запаса — для текста под полосой запаса ("3 патрона", "120 сек"). */
  unit: string;
  /** Сколько remaining добавляет одна покупка (= "полный бак" для шкалы запаса). */
  rechargeAmount: number;
  baseCost: number;
  /** Рост цены за каждую уже совершённую покупку этого предмета, до growthCap. */
  rebuyGrowth: number;
  growthCap: number;
  /** Не расходуется, нельзя купить второй раз, пока он есть (нет смысла) — оружие
   *  и ключ "владеешь один раз", а не стопкой. */
  singleOwn?: boolean;
}

// Порядок и состав — как на референсе дизайнера (2 ряда по 4): Лопата, Пистолет,
// Фонарь, Аптечка / Лом, Патроны, Бинт, Ключ. Пистолет теперь отдельно от патронов
// (владение оружием — одноразовая покупка, боеприпасы — расходник), как на референсе.
export const ITEMS: readonly ItemDefinition[] = [
  { id: "shovel", title: "Лопата", description: "Нужна для ремонта и раскопок лопатой", category: "tool", unit: "использований", rechargeAmount: 15, baseCost: 300, rebuyGrowth: 0.15, growthCap: 2 },
  { id: "pistol", title: "Пистолет", description: "Базовое оружие — убивает зомби выстрелом", category: "weapon", unit: "шт", rechargeAmount: 1, baseCost: 800, rebuyGrowth: 0, growthCap: 1, singleOwn: true },
  // Предмет "Фонарь" ≠ навык "Фонарь" (SkillSystem) — этот покупает новую лампу,
  // когда старая перегорит (FlashlightSystem.installBulb), навык замедляет расход
  // заряда. Id не "flashlight", чтобы не путать с полем FlashlightSystem в коде.
  { id: "flashlightItem", title: "Фонарь", description: "Освещает тёмные места. Можно улучшать (см. прокачку)", category: "tool", unit: "сек свечения", rechargeAmount: 180, baseCost: 200, rebuyGrowth: 0.15, growthCap: 2 },
  { id: "medkit", title: "Аптечка", description: "Восстанавливает здоровье полностью", category: "consumable", unit: "шт", rechargeAmount: 1, baseCost: 300, rebuyGrowth: 0.08, growthCap: 1.6 },
  // Пока без эффекта — в игре ещё нет запертых дверей/контейнеров, которые он
  // должен открывать (решение: добавить для соответствия референсу, реализовать
  // позже вместе с этой механикой).
  { id: "crowbar", title: "Лом", description: "Открывает закрытые двери и контейнеры", category: "tool", unit: "шт", rechargeAmount: 1, baseCost: 250, rebuyGrowth: 0.1, growthCap: 1.8 },
  { id: "ammo", title: "Патроны", description: "Боеприпасы для пистолета", category: "weapon", unit: "патронов", rechargeAmount: 6, baseCost: 150, rebuyGrowth: 0.12, growthCap: 2.2 },
  { id: "bandage", title: "Бинт", description: "Останавливает кровь, восстанавливает часть здоровья", category: "consumable", unit: "шт", rechargeAmount: 1, baseCost: 100, rebuyGrowth: 0.08, growthCap: 1.6 },
  { id: "key", title: "Ключ", description: "Открывает путь из города — завершает игру", category: "special", unit: "шт", rechargeAmount: 1, baseCost: 2600, rebuyGrowth: 0, growthCap: 1, singleOwn: true },
  // Не на референсе дизайнера (там нет иконки капкана) — оставлен: пользователь
  // отдельно просил его раньше, и это рабочая механика (ZombieSystem.stun()).
  { id: "trap", title: "Капкан", description: "Оглушает зомби при срабатывании", category: "weapon", unit: "шт", rechargeAmount: 1, baseCost: 160, rebuyGrowth: 0.1, growthCap: 1.8 },
];

export type ItemStock = Record<ItemId, number>;
export type ItemPurchaseCounts = Record<ItemId, number>;

function emptyStock(): ItemStock {
  return { shovel: 0, pistol: 0, flashlightItem: 0, medkit: 0, crowbar: 0, ammo: 0, bandage: 0, key: 0, trap: 0 };
}

function emptyPurchaseCounts(): ItemPurchaseCounts {
  return { shovel: 0, pistol: 0, flashlightItem: 0, medkit: 0, crowbar: 0, ammo: 0, bandage: 0, key: 0, trap: 0 };
}

function definition(id: ItemId): ItemDefinition {
  const found = ITEMS.find((item) => item.id === id);
  if (!found) throw new Error(`unknown item ${id}`);
  return found;
}

export class InventorySystem {
  private stock: ItemStock = emptyStock();
  private purchaseCounts: ItemPurchaseCounts = emptyPurchaseCounts();

  load(savedStock: Partial<Record<string, number>> | undefined, savedPurchases: Partial<Record<string, number>> | undefined): void {
    this.stock = emptyStock();
    this.purchaseCounts = emptyPurchaseCounts();
    for (const item of ITEMS) {
      const stockValue = savedStock?.[item.id];
      if (typeof stockValue === "number" && Number.isFinite(stockValue)) {
        this.stock[item.id] = Math.max(0, stockValue);
      }
      const purchaseValue = savedPurchases?.[item.id];
      if (typeof purchaseValue === "number" && Number.isFinite(purchaseValue)) {
        this.purchaseCounts[item.id] = Math.max(0, Math.floor(purchaseValue));
      }
    }
  }

  getStock(): ItemStock {
    return { ...this.stock };
  }

  getPurchaseCounts(): ItemPurchaseCounts {
    return { ...this.purchaseCounts };
  }

  getRemaining(id: ItemId): number {
    return this.stock[id];
  }

  /** null — больше не купить (ключ уже есть). */
  getNextCost(id: ItemId): number | null {
    const item = definition(id);
    if (item.singleOwn && this.stock[id] > 0) return null;
    const growth = Math.min(item.growthCap, Math.pow(1 + item.rebuyGrowth, this.purchaseCounts[id]));
    return Math.round(item.baseCost * growth);
  }

  /** Пополняет запас на rechargeAmount — цену и наличие деньги проверяет вызывающий
   *  (Wallet), как и у SkillSystem.upgrade(). */
  grant(id: ItemId): boolean {
    if (this.getNextCost(id) === null) return false;
    const item = definition(id);
    this.stock[id] += item.rechargeAmount;
    this.purchaseCounts[id] += 1;
    return true;
  }

  /** Тратит amount запаса; false — не хватает (эффект не применяется). */
  consume(id: ItemId, amount = 1): boolean {
    if (this.stock[id] < amount) return false;
    this.stock[id] -= amount;
    return true;
  }
}
