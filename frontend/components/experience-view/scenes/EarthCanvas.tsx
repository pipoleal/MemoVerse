"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";

import Earth from "../Earth";

export default function EarthCanvas() {
  return (
    <div className="absolute inset-0">
      <Canvas
        camera={{
          position: [0, 0, 6],
          fov: 45,
        }}
        dpr={[1, 2]}
        gl={{
          antialias: true,
        }}
      >
        <directionalLight
          position={[5, 3, 5]}
          intensity={2.5}
        />

        <Earth />

        <OrbitControls
          enableZoom={false}
          enablePan={false}
          enableRotate={false}
        />
      </Canvas>
    </div>
  );
}