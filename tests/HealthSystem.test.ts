import { describe, expect, it } from "vitest";
import { HealthSystem } from "@/systems/HealthSystem";

describe("HealthSystem", () => {
  it("starts at full health", () => {
    const health = new HealthSystem();
    expect(health.getHealthPercent()).toBe(100);
    expect(health.isDead()).toBe(false);
  });

  it("drains proportionally to the damage rate and elapsed time", () => {
    const health = new HealthSystem();
    health.damage(20, 2); // 40 урона
    expect(health.getHealthPercent()).toBeCloseTo(60, 5);
  });

  it("never goes below 0", () => {
    const health = new HealthSystem();
    health.damage(1000, 1);
    expect(health.getHealthPercent()).toBe(0);
    expect(health.isDead()).toBe(true);
  });

  it("does nothing when the damage rate is 0 (no source of damage this frame)", () => {
    const health = new HealthSystem();
    health.damage(20, 1);
    const before = health.getHealthPercent();
    health.damage(0, 1);
    expect(health.getHealthPercent()).toBe(before);
  });

  it("heal() restores health but never above the max", () => {
    const health = new HealthSystem();
    health.damage(50, 1);
    health.heal(20);
    expect(health.getHealthPercent()).toBeCloseTo(70, 5);
    health.heal(1000);
    expect(health.getHealthPercent()).toBe(100);
  });

  it("reset() restores full health", () => {
    const health = new HealthSystem();
    health.damage(1000, 1);
    expect(health.isDead()).toBe(true);
    health.reset();
    expect(health.getHealthPercent()).toBe(100);
    expect(health.isDead()).toBe(false);
  });
});
