import { describe, expect, it } from "vitest";
import { InventorySystem } from "@/systems/InventorySystem";

describe("InventorySystem", () => {
  it("starts empty", () => {
    const inventory = new InventorySystem();
    expect(inventory.getRemaining("bandage")).toBe(0);
    expect(inventory.getNextCost("bandage")).toBe(100);
  });

  it("grant() tops up stock by the item's recharge amount", () => {
    const inventory = new InventorySystem();
    inventory.grant("shovel");
    expect(inventory.getRemaining("shovel")).toBe(15);
    inventory.grant("shovel");
    expect(inventory.getRemaining("shovel")).toBe(30);
  });

  it("rebuy price grows with each purchase, capped at growthCap", () => {
    const inventory = new InventorySystem();
    const first = inventory.getNextCost("ammo")!;
    inventory.grant("ammo");
    const second = inventory.getNextCost("ammo")!;
    expect(second).toBeGreaterThan(first);

    for (let i = 0; i < 20; i++) inventory.grant("ammo");
    const capped = inventory.getNextCost("ammo")!;
    expect(capped).toBe(Math.round(150 * 2.2));
  });

  it("consume() only spends what is available", () => {
    const inventory = new InventorySystem();
    inventory.grant("bandage");
    expect(inventory.consume("bandage", 2)).toBe(false);
    expect(inventory.consume("bandage", 1)).toBe(true);
    expect(inventory.getRemaining("bandage")).toBe(0);
  });

  it("key and pistol are single-own: cannot be bought again once owned", () => {
    const inventory = new InventorySystem();
    expect(inventory.getNextCost("key")).toBe(2600);
    inventory.grant("key");
    expect(inventory.getRemaining("key")).toBe(1);
    expect(inventory.getNextCost("key")).toBeNull();
    expect(inventory.grant("key")).toBe(false);

    expect(inventory.getNextCost("pistol")).toBe(800);
    inventory.grant("pistol");
    expect(inventory.getNextCost("pistol")).toBeNull();
    expect(inventory.grant("pistol")).toBe(false);
  });

  it("loads saved stock and purchase counts, clamping junk", () => {
    const inventory = new InventorySystem();
    inventory.load({ bandage: 3, medkit: -2 }, { bandage: 2 });
    expect(inventory.getRemaining("bandage")).toBe(3);
    expect(inventory.getRemaining("medkit")).toBe(0);
    const priceAfterTwoPurchases = inventory.getNextCost("bandage")!;
    expect(priceAfterTwoPurchases).toBeGreaterThan(100);
  });
});
