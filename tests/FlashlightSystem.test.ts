import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { FlashlightSystem } from "@/systems/FlashlightSystem";

describe("FlashlightSystem", () => {
  it("aims the beam along the view direction, not down at the feet", () => {
    const camera = new THREE.PerspectiveCamera();
    camera.position.set(0, 1.6, 0);
    const flashlight = new FlashlightSystem();
    flashlight.attachToCamera(camera);
    camera.updateMatrixWorld(true);

    const origin = flashlight.light.getWorldPosition(new THREE.Vector3());
    const target = flashlight.light.target.getWorldPosition(new THREE.Vector3());
    const beam = target.sub(origin).normalize();

    // Фонарь у глаз (в руке), а не на метр выше камеры.
    expect(Math.abs(origin.y - 1.6)).toBeLessThan(0.5);
    // Луч почти параллелен взгляду (-Z): угол меньше ~3°.
    expect(beam.dot(new THREE.Vector3(0, 0, -1))).toBeGreaterThan(Math.cos(THREE.MathUtils.degToRad(3)));
  });

  it("the bulb burns out after its lifetime and blocks toggle() until a spare is installed", () => {
    const flashlight = new FlashlightSystem();
    flashlight.installBulb(1);
    flashlight.toggle();
    expect(flashlight.isOn()).toBe(true);

    flashlight.update(1);
    expect(flashlight.isBulbBurnedOut()).toBe(true);
    expect(flashlight.isOn()).toBe(false);

    flashlight.toggle();
    expect(flashlight.isOn()).toBe(false);

    flashlight.installBulb(60);
    expect(flashlight.isBulbBurnedOut()).toBe(false);
    flashlight.toggle();
    expect(flashlight.isOn()).toBe(true);
  });
});
