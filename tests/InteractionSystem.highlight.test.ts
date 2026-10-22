import { describe, expect, it } from "vitest";
import * as THREE from "three";
import type { SceneManager } from "@/core/SceneManager";
import { InteractionSystem } from "@/systems/InteractionSystem";
import { ObjectStateMachine } from "@/systems/ObjectStateMachine";
import { ShiftManager } from "@/systems/ShiftManager";

// Надгробие и его земля — один объект (одна модель), но светятся они ПО ОТДЕЛЬНОСТИ: земля помечена
// extras материала nk_highlight = "earth" (так её экспортирует grave_mound_props.py).
function makeGrave() {
  const stoneMaterial = new THREE.MeshStandardMaterial();
  const earthMaterial = new THREE.MeshStandardMaterial();
  earthMaterial.userData.nk_highlight = "earth";
  const stone = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.8, 0.2), stoneMaterial);
  stone.position.set(0, 0.4, 0);
  const earth = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.1, 2), earthMaterial);
  earth.position.set(0, 0.05, 1.3);
  const root = new THREE.Group();
  root.userData.instanceId = "g1";
  root.add(stone, earth);
  root.updateMatrixWorld(true);
  return { root, stone, earth, stoneMaterial, earthMaterial };
}

function makeInteraction(lookAt: THREE.Vector3, from: THREE.Vector3) {
  const camera = new THREE.PerspectiveCamera();
  camera.position.copy(from);
  camera.lookAt(lookAt);
  camera.updateMatrixWorld(true);
  const stateMachine = new ObjectStateMachine();
  return new InteractionSystem(camera, stateMachine, new ShiftManager(stateMachine), {} as SceneManager);
}

describe("раздельная подсветка частей объекта", () => {
  it("смотришь на камень — светится только камень", () => {
    const { root, stone, earth, stoneMaterial, earthMaterial } = makeGrave();
    const interaction = makeInteraction(new THREE.Vector3(0, 0.5, 0), new THREE.Vector3(0, 0.5, 3));
    interaction.update([root], false, 0.016);

    expect(interaction.getFocused()).toBe(root);
    expect(stone.material).not.toBe(stoneMaterial);
    expect((stone.material as THREE.MeshStandardMaterial).emissiveIntensity).toBeGreaterThan(0);
    expect(earth.material).toBe(earthMaterial);
  });

  it("смотришь на землю — светится только земля, а объект в фокусе тот же (E работает как у надгробия)", () => {
    const { root, stone, earth, stoneMaterial, earthMaterial } = makeGrave();
    const interaction = makeInteraction(new THREE.Vector3(0, 0.1, 1.3), new THREE.Vector3(0, 1.5, 2.6));
    interaction.update([root], false, 0.016);

    expect(interaction.getFocused()).toBe(root);
    expect(earth.material).not.toBe(earthMaterial);
    expect(stone.material).toBe(stoneMaterial);
  });

  it("переход с земли на камень переключает подсветку и возвращает материалы", () => {
    const { root, stone, earth, stoneMaterial, earthMaterial } = makeGrave();
    const camera = new THREE.PerspectiveCamera();
    const stateMachine = new ObjectStateMachine();
    const interaction = new InteractionSystem(camera, stateMachine, new ShiftManager(stateMachine), {} as SceneManager);

    camera.position.set(0, 1.5, 2.6);
    camera.lookAt(0, 0.1, 1.3);
    camera.updateMatrixWorld(true);
    interaction.update([root], false, 0.016);
    expect(earth.material).not.toBe(earthMaterial);

    camera.position.set(0, 0.5, 3);
    camera.lookAt(0, 0.5, 0);
    camera.updateMatrixWorld(true);
    interaction.update([root], false, 0.016);

    expect(earth.material).toBe(earthMaterial);
    expect(stone.material).not.toBe(stoneMaterial);
  });

  it("объект без помеченных частей светится целиком, как раньше", () => {
    const a = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.4, 0.4), new THREE.MeshStandardMaterial());
    const b = new THREE.Mesh(new THREE.BoxGeometry(0.4, 0.4, 0.4), new THREE.MeshStandardMaterial());
    b.position.set(0, 0.5, 0);
    const root = new THREE.Group();
    root.userData.instanceId = "wreath1";
    root.add(a, b);
    root.updateMatrixWorld(true);
    const materialA = a.material;
    const materialB = b.material;
    const interaction = makeInteraction(new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 3));
    interaction.update([root], false, 0.016);

    expect(a.material).not.toBe(materialA);
    expect(b.material).not.toBe(materialB);
  });
});
