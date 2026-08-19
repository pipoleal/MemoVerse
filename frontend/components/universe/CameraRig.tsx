"use client";

import { useFrame } from "@react-three/fiber";

export default function CameraRig() {
  useFrame(({ camera, clock }) => {
    const t = clock.getElapsedTime();

    camera.position.x = Math.sin(t * 0.08) * 2;

    camera.position.y = Math.cos(t * 0.06) * 1;

    camera.lookAt(0, 0, 0);
  });

  return null;
}