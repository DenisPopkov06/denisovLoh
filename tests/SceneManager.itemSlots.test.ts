import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { SceneManager } from "@/core/SceneManager";
import type { AssetLoader } from "@/core/AssetLoader";
import { ObjectStateMachine } from "@/systems/ObjectStateMachine";
import { ObjectState, type ZoneLayout } from "@/data/types";

// В node-окружении нет DOM — небу в конструкторе SceneManager нечем грузить текстуру.
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  return { ...actual, TextureLoader: class { load(): void {} } };
});

function makeLoader(): AssetLoader {
  return { loadModel: () => Promise.resolve({ scene: new THREE.Group(), animations: [] }) } as unknown as AssetLoader;
}

// Два надгробия далеко друг от друга, с горшком/цветами, изначально поставленными
// дизайнером по-разному относительно своего камня (сбоку у g1, сзади у g2) — именно
// это пользователь описал как баг: "у каждого надгробия по-разному стоят предметы".
const LAYOUT: ZoneLayout = {
  zoneId: "test",
  modelPath: "models/zone_test.glb",
  spawnPoint: { x: 0, y: 0, z: 0 },
  objects: [
    { instanceId: "g1", objectId: "gravestone_cross_a", position: { x: 0, y: 0, z: 0 }, rotationY: 0, defaultState: ObjectState.NORMAL },
    { instanceId: "pot1", objectId: "pot_clay_a", position: { x: 0.9, y: 0, z: -0.2 }, rotationY: 0, defaultState: ObjectState.NORMAL },
    { instanceId: "flowers1", objectId: "flowers_daisy_a", position: { x: -0.1, y: 0, z: 0.9 }, rotationY: 0, defaultState: ObjectState.NORMAL },

    { instanceId: "g2", objectId: "gravestone_slab_a", position: { x: 30, y: 0, z: -30 }, rotationY: 90, defaultState: ObjectState.NORMAL },
    { instanceId: "pot2", objectId: "pot_clay_a", position: { x: 29.1, y: 0, z: -30.9 }, rotationY: 0, defaultState: ObjectState.NORMAL },
    { instanceId: "flowers2", objectId: "flowers_poppy_a", position: { x: 30.9, y: 0, z: -29.8 }, rotationY: 0, defaultState: ObjectState.NORMAL },
  ],
};

describe("SceneManager: однотипное расположение предметов у каждого надгробия", () => {
  it("горшок и цветы снимаются с исходной авторской позиции и встают в единый слот относительно своего камня", async () => {
    const manager = new SceneManager(makeLoader(), new ObjectStateMachine());
    await manager.loadZone(LAYOUT);
    manager.reshufflePlacedObjects();

    const layout = manager.getCurrentLayout()!;
    const byId = new Map(layout.objects.map((o) => [o.instanceId, o]));

    function localOffset(itemId: string, graveId: string) {
      const item = byId.get(itemId)!;
      const grave = byId.get(graveId)!;
      const dx = item.position.x - grave.position.x;
      const dz = item.position.z - grave.position.z;
      const rad = THREE.MathUtils.degToRad(grave.rotationY);
      const cos = Math.cos(-rad);
      const sin = Math.sin(-rad);
      return { x: dx * cos - dz * sin, z: dx * sin + dz * cos };
    }

    const pot1 = localOffset("pot1", "g1");
    const pot2 = localOffset("pot2", "g2");
    const flowers1 = localOffset("flowers1", "g1");
    const flowers2 = localOffset("flowers2", "g2");

    // Один и тот же локальный слот у ОБОИХ камней, несмотря на разные авторские
    // позиции и разный поворот камня (g1: 0°, g2: 90°).
    expect(pot1.x).toBeCloseTo(pot2.x, 5);
    expect(pot1.z).toBeCloseTo(pot2.z, 5);
    expect(flowers1.x).toBeCloseTo(flowers2.x, 5);
    expect(flowers1.z).toBeCloseTo(flowers2.z, 5);

    // Горшок и цветы не встали в одну точку (слоты разнесены).
    expect(Math.hypot(pot1.x - flowers1.x, pot1.z - flowers1.z)).toBeGreaterThan(0.3);
  });

  it("DISPLACED по-прежнему сдвигает горшок в сторону от (уже нормализованного) слота", async () => {
    const stateMachine = new ObjectStateMachine();
    const manager = new SceneManager(makeLoader(), stateMachine);
    await manager.loadZone(LAYOUT);
    manager.reshufflePlacedObjects();

    const slotBefore = manager.getAnchorTransform("pot1")!;

    stateMachine.transition("pot1", ObjectState.DISPLACED);
    await new Promise((resolve) => setTimeout(resolve, 10));

    const pot = manager.getObjectByInstanceId("pot1")!;
    const dist = Math.hypot(pot.position.x - slotBefore.position.x, pot.position.z - slotBefore.position.z);
    expect(dist).toBeGreaterThan(0.5); // явно в стороне от слота, не на месте
  });
});
