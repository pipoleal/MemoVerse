"use client";

import {
  AdditiveBlending,
  BackSide,
} from "three";

export default function Atmosphere() {
  return (
    <mesh scale={[1.025, 1.025, 1.025]}>
      <sphereGeometry args={[2, 128, 128]} />

      <meshBasicMaterial
        color="#58a6ff"
        transparent
        opacity={0.08}
        blending={AdditiveBlending}
        side={BackSide}
        depthWrite={false}
      />
    </mesh>
  );
}