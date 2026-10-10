import { describe, expect, it, vi } from "vitest";
import * as THREE from "three";
import { SceneManager } from "@/core/SceneManager";
import { InteractionSystem } from "@/systems/InteractionSystem";
import { ObjectStateMachine } from "@/systems/ObjectStateMachine";
import { ShiftManager } from "@/systems/ShiftManager";
import type { AssetLoader } from "@/core/AssetLoader";
import { ObjectState, type ZoneLayout } from "@/data/types";

// В node-окружении нет DOM — небу в конструкторе SceneManager нечем грузить текстуру.
vi.mock("three", async (importOriginal) => {
  const actual = await importOriginal<typeof import("three")>();
  return { ...actual, TextureLoader: class { load(): void {} } };
});

const LAYOUT: ZoneLayout = {
  zoneId: "test",
  modelPath: "models/zone_test.glb",
  spawnPoint: { x: 0, y: 0, z: 0 },
  objects: [
    { instanceId: "g1", objectId: "gravestone_cross_a", position: { x: 0, y: 0, z: 0 }, rotationY: 0, defaultState: ObjectState.NORMAL },
    { instanceId: "pot1", objectId: "pot_clay_a", position: { x: 1.5, y: 0, z: -1.5 }, rotationY: 0, defaultState: ObjectState.NORMAL },
  ],
};

function makeLoader(): AssetLoader {
  return { loadModel: () => Promise.resolve({ scene: new THREE.Group(), animations: [] }) } as unknown as AssetLoader;
}

/** Настраивает сцену с одним надгробием и горшком (уже расставленным по слоту ITEM_SLOTS
 * через reshufflePlacedObjects), InteractionSystem, где горшок УЖЕ "в руках" у игрока
 * (минуя подбор/наведение — они не часть этого теста). */
async function setup() {
  const stateMachine = new ObjectStateMachine();
  const shiftManager = new ShiftManager(stateMachine);
  const sceneManager = new SceneManager(makeLoader(), stateMachine);
  await sceneManager.loadZone(LAYOUT);
  sceneManager.reshufflePlacedObjects(); // расставляет pot1 в слот "справа спереди" у g1

  const camera = new THREE.PerspectiveCamera();
  const interaction = new InteractionSystem(camera, stateMachine, shiftManager, sceneManager);

  stateMachine.transition("pot1", ObjectState.MISSING); // как будто игрок уже его подобрал

  const potObject = sceneManager.getObjectByInstanceId("pot1")!;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (interaction as any).carriedObject = potObject;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (interaction as any).carriedInstanceId = "pot1";

  const anchor = sceneManager.getAnchorTransform("pot1")!;
  return { stateMachine, sceneManager, interaction, camera, anchor };
}

describe("InteractionSystem: куда реально можно поставить переносимый предмет", () => {
  it("засчитывает постановку, когда игрок стоит у ПРАВИЛЬНОЙ стороны камня (у слота предмета)", async () => {
    const { stateMachine, interaction, camera, anchor } = await setup();

    // Игрок стоит максимально близко к слоту (но не ВНУТРИ камня — упирается в его
    // коллизию, ~0.75м от центра камня в реальной игре; здесь просто у самого якоря).
    camera.position.set(anchor.position.x + 0.1, 1.6, anchor.position.z + 0.1);
    interaction.interact();

    expect(stateMachine.getState("pot1")).toBe(ObjectState.NORMAL);
  });

  it("НЕ засчитывает постановку с противоположной стороны камня, хоть и рядом с ним", async () => {
    const { stateMachine, interaction, camera } = await setup();

    // Слот горшка — (0.45, 0.25) от центра g1 (ITEM_SLOTS.pot); противоположная точка
    // у камня — примерно (-0.45, -0.25), на таком же расстоянии от камня, но не от слота.
    camera.position.set(-0.45, 1.6, -0.25);
    interaction.interact();

    expect(stateMachine.getState("pot1")).toBe(ObjectState.MISSING);
  });
});
