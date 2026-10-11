import { describe, expect, it } from "vitest";
import {
  LIGHTING_CONFIG,
  ambientIntensityForShift,
  localLightFactorForShift,
  moonIntensityForShift,
  skyBackgroundIntensityForShift,
} from "@/render/Lighting";
import { ZOMBIE_APPEARS_AT_SHIFT } from "@/systems/DifficultyScaler";

describe("ambientIntensityForShift", () => {
  it("matches the base config on shift 1 (no darkening yet)", () => {
    expect(ambientIntensityForShift(1)).toBeCloseTo(LIGHTING_CONFIG.ambientIntensity, 5);
  });

  it("decreases monotonically through shifts 1-3 (before the zombie resets the ramp)", () => {
    const values = [1, 2, 3].map(ambientIntensityForShift);
    for (let i = 1; i < values.length; i++) expect(values[i]).toBeLessThan(values[i - 1]);
  });

  it("is already noticeably dimmer by shift 3 (regression: must not still look fully lit mid-ramp)", () => {
    expect(ambientIntensityForShift(3)).toBeLessThan(LIGHTING_CONFIG.ambientIntensity * 0.55);
  });

  it("is as bright as shift 1 again on the shift the zombie appears (player must see the new threat clearly)", () => {
    expect(ambientIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT)).toBeCloseTo(LIGHTING_CONFIG.ambientIntensity, 5);
  });

  it("decreases monotonically again for the 3 shifts after the zombie appears, then holds a floor", () => {
    const shifts = [0, 1, 2, 3].map((n) => ZOMBIE_APPEARS_AT_SHIFT + n);
    const values = shifts.map(ambientIntensityForShift);
    for (let i = 1; i < values.length - 1; i++) expect(values[i]).toBeLessThan(values[i - 1]);
    expect(values[values.length - 1]).toBeCloseTo(values[values.length - 2], 5);
  });

  it("never goes below the floor (pure dimming, not pitch black)", () => {
    expect(ambientIntensityForShift(50)).toBeGreaterThan(0);
  });
});

describe("moonIntensityForShift", () => {
  it("matches the base config on shift 1", () => {
    expect(moonIntensityForShift(1)).toBeCloseTo(LIGHTING_CONFIG.moonIntensity, 5);
  });

  it("is already noticeably dimmer by shift 3", () => {
    expect(moonIntensityForShift(3)).toBeLessThan(LIGHTING_CONFIG.moonIntensity * 0.55);
  });

  it("resets to full brightness when the zombie appears and dims again, then holds", () => {
    expect(moonIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT)).toBeCloseTo(LIGHTING_CONFIG.moonIntensity, 5);
    expect(moonIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT + 2)).toBeLessThan(
      moonIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT),
    );
    expect(moonIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT + 10)).toBeCloseTo(
      moonIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT + 2),
      5,
    );
  });
});

describe("localLightFactorForShift (фонарь на столбе, окна/лампа дома)", () => {
  it("is 1 (full brightness) on shift 1", () => {
    expect(localLightFactorForShift(1)).toBeCloseTo(1, 5);
  });

  it("is 1 (full brightness) again on the shift the zombie appears", () => {
    expect(localLightFactorForShift(ZOMBIE_APPEARS_AT_SHIFT)).toBeCloseTo(1, 5);
  });

  it("decreases monotonically for the 3 shifts after the zombie appears and then holds at a dim, non-zero floor", () => {
    const shifts = [0, 1, 2, 3].map((n) => ZOMBIE_APPEARS_AT_SHIFT + n);
    const values = shifts.map(localLightFactorForShift);
    for (let i = 1; i < values.length - 1; i++) expect(values[i]).toBeLessThan(values[i - 1]);
    const floor = values[values.length - 1];
    expect(floor).toBeGreaterThan(0);
    expect(floor).toBeLessThan(0.2);
    expect(localLightFactorForShift(ZOMBIE_APPEARS_AT_SHIFT + 20)).toBeCloseTo(floor, 5);
  });
});

describe("skyBackgroundIntensityForShift", () => {
  it("is 1 (full brightness) on shift 1", () => {
    expect(skyBackgroundIntensityForShift(1)).toBeCloseTo(1, 5);
  });

  it("is 1 (full brightness) again on the shift the zombie appears, then dims to a floor and holds", () => {
    expect(skyBackgroundIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT)).toBeCloseTo(1, 5);
    const floor = skyBackgroundIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT + 2);
    expect(floor).toBeGreaterThan(0);
    expect(floor).toBeLessThan(1);
    expect(skyBackgroundIntensityForShift(ZOMBIE_APPEARS_AT_SHIFT + 20)).toBeCloseTo(floor, 5);
  });
});
