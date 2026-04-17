/**
 * Camera preset positioning for 3D point cloud viewer.
 * Z-up convention for UTM/geographic coordinates.
 */

import * as THREE from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export interface BoundingBox3D {
  min: [number, number, number];
  max: [number, number, number];
}

export function applyCameraPreset(
  preset: "orbit" | "top" | "side",
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  bounds: BoundingBox3D,
): void {
  const center = new THREE.Vector3(
    (bounds.min[0] + bounds.max[0]) / 2,
    (bounds.min[1] + bounds.max[1]) / 2,
    (bounds.min[2] + bounds.max[2]) / 2,
  );
  const size = Math.max(
    bounds.max[0] - bounds.min[0],
    bounds.max[1] - bounds.min[1],
    bounds.max[2] - bounds.min[2],
  );
  const dist = size * 1.5;

  switch (preset) {
    case "top":
      camera.position.set(center.x, center.y, center.z + dist);
      break;
    case "side":
      camera.position.set(center.x, center.y - dist, center.z + size * 0.3);
      break;
    case "orbit":
    default:
      camera.position.set(
        center.x + dist * 0.7,
        center.y - dist * 0.7,
        center.z + dist * 0.7,
      );
      break;
  }
  controls.target.copy(center);
  camera.lookAt(center);
  controls.update();
}

export function centerOnHeap(
  camera: THREE.PerspectiveCamera,
  controls: OrbitControls,
  heap: {
    bboxMinE: number;
    bboxMinN: number;
    bboxMaxE: number;
    bboxMaxN: number;
    maxHeight: number;
    baseElevation: number;
  },
): void {
  const center = new THREE.Vector3(
    (heap.bboxMinE + heap.bboxMaxE) / 2,
    (heap.bboxMinN + heap.bboxMaxN) / 2,
    heap.baseElevation + heap.maxHeight / 2,
  );
  const size = Math.max(
    heap.bboxMaxE - heap.bboxMinE,
    heap.bboxMaxN - heap.bboxMinN,
    heap.maxHeight,
  );
  const dist = size * 2.5;
  const offset = camera.position
    .clone()
    .sub(controls.target)
    .normalize()
    .multiplyScalar(dist);
  camera.position.copy(center).add(offset);
  controls.target.copy(center);
  controls.update();
}
