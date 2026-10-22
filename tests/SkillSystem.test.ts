import { describe, expect, it } from "vitest";
import { SkillSystem, SKILL_MAX_LEVEL, SKILLS } from "@/systems/SkillSystem";
import { WalletSystem, TASK_REWARD, shiftCompletionBonus } from "@/systems/WalletSystem";

describe("SkillSystem", () => {
  it("starts at level 0 with x1 multipliers", () => {
    const skills = new SkillSystem();
    for (const skill of SKILLS) {
      expect(skills.getLevel(skill.id)).toBe(0);
      expect(skills.getMultiplier(skill.id)).toBe(1);
    }
  });

  it("each level adds its percent to the multiplier and raises the price", () => {
    const skills = new SkillSystem();
    const first = skills.getUpgradeCost("run")!;
    skills.upgrade("run");
    skills.upgrade("run");
    expect(skills.getMultiplier("run")).toBeCloseTo(1.2);
    expect(skills.getUpgradeCost("run")!).toBeGreaterThan(first);
  });

  it("stops at the max level: no price, upgrade() refuses", () => {
    const skills = new SkillSystem();
    for (let i = 0; i < SKILL_MAX_LEVEL; i++) expect(skills.upgrade("jump")).toBe(true);
    expect(skills.isMaxed("jump")).toBe(true);
    expect(skills.getUpgradeCost("jump")).toBeNull();
    expect(skills.upgrade("jump")).toBe(false);
    expect(skills.getLevel("jump")).toBe(SKILL_MAX_LEVEL);
  });

  it("loads saved levels, clamping junk values", () => {
    const skills = new SkillSystem();
    skills.load({ run: 3, health: 99, stamina: -2, nonsense: 4 });
    expect(skills.getLevel("run")).toBe(3);
    expect(skills.getLevel("health")).toBe(SKILL_MAX_LEVEL);
    expect(skills.getLevel("stamina")).toBe(0);
    expect(Object.keys(skills.getLevels())).not.toContain("nonsense");
  });
});

describe("WalletSystem", () => {
  it("only spends what it has", () => {
    const wallet = new WalletSystem();
    wallet.add(TASK_REWARD);
    expect(wallet.trySpend(TASK_REWARD + 1)).toBe(false);
    expect(wallet.getCoins()).toBe(TASK_REWARD);
    expect(wallet.trySpend(TASK_REWARD)).toBe(true);
    expect(wallet.getCoins()).toBe(0);
  });

  it("shift bonus grows with the shift number", () => {
    expect(shiftCompletionBonus(3)).toBeGreaterThan(shiftCompletionBonus(1));
  });
});
