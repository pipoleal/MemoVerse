"use client";

import { Canvas } from "@react-three/fiber";

import Scene from "./Scene";

export default function Universe() {
  return (
    <div className="absolute inset-0 -z-10">
      <Canvas
        camera={{
          position: [0, 0, 12],
          fov: 65,
        }}
      >
        <Scene />
      </Canvas>
    </div>
  );
}