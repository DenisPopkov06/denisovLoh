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
    { instanceId: "flowers1", objectId: "flowers_daisy_a", position: { x: -1.5, y: 0, z: 1.5 }, rotationY: 0, defaultState: ObjectState.NORMAL },
  ],
};

function makeLoader(): AssetLoader {
  return { loadModel: () => Promise.resolve({ scene: new THREE.Group(), animations: [] }) } as unknown as AssetLoader;
}

/** Настраивает сцену с одним надгробием и всеми переносимыми предметами (уже
 * расставленными по слотам ITEM_SLOTS через reshufflePlacedObjects), InteractionSystem,
 * где указанный предмет УЖЕ "в руках" у игрока (минуя подбор/наведение — они не часть
 * этого теста). Общая логика постановки (радиус, слот) не зависит от типа предмета —
 * поэтому один и тот же сетап обслуживает и горшок, и цветы. */
async function setup(carriedInstanceId: string) {
  const stateMachine = new ObjectStateMachine();
  const shiftManager = new ShiftManager(stateMachine);
  const sceneManager = new SceneManager(makeLoader(), stateMachine);
  await sceneManager.loadZone(LAYOUT);
  sceneManager.reshufflePlacedObjects(); // расставляет оба предмета по их слотам у g1

  const camera = new THREE.PerspectiveCamera();
  const interaction = new InteractionSystem(camera, stateMachine, shiftManager, sceneManager);

  stateMachine.transition(carriedInstanceId, ObjectState.MISSING); // как будто игрок уже подобрал

  const object = sceneManager.getObjectByInstanceId(carriedInstanceId)!;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (interaction as any).carriedObject = object;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (interaction as any).carriedInstanceId = carriedInstanceId;

  const anchor = sceneManager.getAnchorTransform(carriedInstanceId)!;
  return { stateMachine, sceneManager, interaction, camera, anchor };
}

describe.each([
  { label: "горшок", instanceId: "pot1", oppositeOf: { x: -0.45, z: -0.25 } }, // ITEM_SLOTS.pot = (0.45, 0.25)
  { label: "цветы", instanceId: "flowers1", oppositeOf: { x: 0.45, z: -0.25 } }, // ITEM_SLOTS.flowers = (-0.45, 0.25)
])("InteractionSystem: куда реально можно поставить $label", ({ instanceId, oppositeOf }) => {
  it("засчитывает постановку, когда игрок стоит у ПРАВИЛЬНОЙ стороны камня (у слота предмета)", async () => {
    const { stateMachine, interaction, camera, anchor } = await setup(instanceId);

    // Игрок стоит максимально близко к слоту (но не ВНУТРИ камня — упирается в его
    // коллизию, ~0.75м от центра камня в реальной игре; здесь просто у самого якоря).
    camera.position.set(anchor.position.x + 0.1, 1.6, anchor.position.z + 0.1);
    interaction.interact();

    expect(stateMachine.getState(instanceId)).toBe(ObjectState.NORMAL);
  });

  it("НЕ засчитывает постановку с противоположной стороны камня, хоть и рядом с ним", async () => {
    const { stateMachine, interaction, camera } = await setup(instanceId);

    // Точка на таком же расстоянии от камня, что и слот, но с противоположной стороны.
    camera.position.set(oppositeOf.x, 1.6, oppositeOf.z);
    interaction.interact();

    expect(stateMachine.getState(instanceId)).toBe(ObjectState.MISSING);
  });
});
