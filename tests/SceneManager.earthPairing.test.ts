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

// Три надгробия с разным поворотом и по своей земле (earth_N на месте камня g_N): после перемешивания камней
// каждая земля должна стоять там же, где ЕЁ камень, и с тем же поворотом — в layout и на сцене.
const LAYOUT: ZoneLayout = {
  zoneId: "test",
  modelPath: "models/zone_test.glb",
  spawnPoint: { x: 0, y: 0, z: 0 },
  objects: [
    { instanceId: "g1", objectId: "gravestone_cross_a", position: { x: 0, y: 0, z: 0 }, rotationY: 0, defaultState: ObjectState.NORMAL },
    { instanceId: "g2", objectId: "gravestone_arch_a", position: { x: 10, y: 0, z: -4 }, rotationY: 90, defaultState: ObjectState.NORMAL },
    { instanceId: "g3", objectId: "gravestone_slab_a", position: { x: -7, y: 0, z: 9 }, rotationY: 215, defaultState: ObjectState.NORMAL },
    { instanceId: "earth1", objectId: "grave_earth_a", position: { x: 0, y: 0, z: 0 }, rotationY: 0, defaultState: ObjectState.NORMAL },
    { instanceId: "earth2", objectId: "grave_earth_a", position: { x: 10, y: 0, z: -4 }, rotationY: 90, defaultState: ObjectState.NORMAL },
    { instanceId: "earth3", objectId: "grave_earth_a", position: { x: -7, y: 0, z: 9 }, rotationY: 215, defaultState: ObjectState.NORMAL },
  ],
};

describe("SceneManager: земля у надгробия ходит за своим камнем", () => {
  it("после любого перемешивания земля стоит там же и с тем же поворотом, что её камень", async () => {
    const manager = new SceneManager(makeLoader(), new ObjectStateMachine());
    await manager.loadZone(LAYOUT);

    for (let round = 0; round < 8; round++) {
      manager.reshufflePlacedObjects();
      const byId = new Map(manager.getCurrentLayout()!.objects.map((o) => [o.instanceId, o]));
      for (const n of [1, 2, 3]) {
        const grave = byId.get(`g${n}`)!;
        const earth = byId.get(`earth${n}`)!;
        expect(earth.position.x).toBeCloseTo(grave.position.x, 9);
        expect(earth.position.z).toBeCloseTo(grave.position.z, 9);
        expect(earth.rotationY).toBeCloseTo(grave.rotationY, 9);

        const graveObject = manager.getObjectByInstanceId(`g${n}`)!;
        const earthObject = manager.getObjectByInstanceId(`earth${n}`)!;
        expect(earthObject.position.distanceTo(graveObject.position)).toBeLessThan(1e-9);
        expect(earthObject.rotation.y).toBeCloseTo(graveObject.rotation.y, 9);
      }
    }
  });

  it("земля — декор: не участвует в перемешивании как надгробие и не интерактивна", async () => {
    const manager = new SceneManager(makeLoader(), new ObjectStateMachine());
    await manager.loadZone(LAYOUT);
    manager.reshufflePlacedObjects();

    const interactable = manager.getInteractableObjects().map((o) => o.userData.instanceId);
    expect(interactable).not.toContain("earth1");
    expect(interactable).toEqual(expect.arrayContaining(["g1", "g2", "g3"]));
  });
});
