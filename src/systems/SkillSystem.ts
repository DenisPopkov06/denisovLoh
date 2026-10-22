/** Прокачка навыков (магазин у дома, ShopScreen): у каждого навыка уровни 0..MAX,
 *  цена следующего уровня растёт линейно, эффект — процент за уровень к базовому
 *  значению соответствующей системы (см. Game.applySkillEffects). */
export type SkillId = "run" | "jump" | "flashlight" | "health" | "stamina" | "lockpick";

export interface SkillDefinition {
  id: SkillId;
  title: string;
  /** Текст эффекта для одного уровня — как на референсе магазина. */
  description: string;
  percentPerLevel: number;
  baseCost: number;
  costPerLevel: number;
}

export const SKILL_MAX_LEVEL = 5;

export const SKILLS: readonly SkillDefinition[] = [
  { id: "run", title: "Бег", description: "Скорость бега увеличивается на 10%", percentPerLevel: 10, baseCost: 300, costPerLevel: 100 },
  { id: "jump", title: "Прыжок", description: "Высота прыжка увеличивается на 15%", percentPerLevel: 15, baseCost: 300, costPerLevel: 100 },
  { id: "flashlight", title: "Фонарь", description: "Длительность работы увеличивается на 20%", percentPerLevel: 20, baseCost: 200, costPerLevel: 100 },
  { id: "health", title: "Здоровье", description: "Макс. здоровье увеличивается на 20%", percentPerLevel: 20, baseCost: 700, costPerLevel: 150 },
  { id: "stamina", title: "Выносливость", description: "Восстанавливается быстрее на 15%", percentPerLevel: 15, baseCost: 300, costPerLevel: 100 },
  // Замков в игре пока нет — "взлом" ускоряет всё, что делается удержанием E (ремонт).
  { id: "lockpick", title: "Взлом", description: "Работа с удержанием E быстрее на 25%", percentPerLevel: 25, baseCost: 800, costPerLevel: 150 },
];

export type SkillLevels = Record<SkillId, number>;

function emptyLevels(): SkillLevels {
  return { run: 0, jump: 0, flashlight: 0, health: 0, stamina: 0, lockpick: 0 };
}

function definition(id: SkillId): SkillDefinition {
  const found = SKILLS.find((s) => s.id === id);
  if (!found) throw new Error(`unknown skill ${id}`);
  return found;
}

export class SkillSystem {
  private levels: SkillLevels = emptyLevels();

  /** Уровни из сохранения — неизвестные ключи игнорируются, значения зажимаются в 0..MAX. */
  load(saved: Partial<Record<string, number>> | undefined): void {
    this.levels = emptyLevels();
    if (!saved) return;
    for (const skill of SKILLS) {
      const value = saved[skill.id];
      if (typeof value === "number" && Number.isFinite(value)) {
        this.levels[skill.id] = Math.max(0, Math.min(SKILL_MAX_LEVEL, Math.floor(value)));
      }
    }
  }

  getLevels(): SkillLevels {
    return { ...this.levels };
  }

  getLevel(id: SkillId): number {
    return this.levels[id];
  }

  isMaxed(id: SkillId): boolean {
    return this.levels[id] >= SKILL_MAX_LEVEL;
  }

  /** Цена следующего уровня; null — навык уже максимальный. */
  getUpgradeCost(id: SkillId): number | null {
    if (this.isMaxed(id)) return null;
    const skill = definition(id);
    return skill.baseCost + skill.costPerLevel * this.levels[id];
  }

  /** Повышает уровень без проверки денег — списание делает вызывающий (Wallet). */
  upgrade(id: SkillId): boolean {
    if (this.isMaxed(id)) return false;
    this.levels[id] += 1;
    return true;
  }

  /** 1 + процент·уровень/100 — во сколько раз навык усиливает базовое значение. */
  getMultiplier(id: SkillId): number {
    return 1 + (definition(id).percentPerLevel * this.levels[id]) / 100;
  }
}
