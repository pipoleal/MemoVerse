"use client";

import { useMemo, useRef } from "react";
import { useFrame, useLoader } from "@react-three/fiber";

import {
  Group,
  LinearMipmapLinearFilter,
  SRGBColorSpace,
  Texture,
  TextureLoader,
} from "three";

import Atmosphere from "./Atmosphere";

export default function Earth() {
  const earthRef = useRef<Group>(null);

  const loadedTexture = useLoader(
    TextureLoader,
    "/textures/earth.jpg"
  ) as Texture;

  const texture = useMemo(() => {
    const clonedTexture = loadedTexture.clone();

    clonedTexture.colorSpace = SRGBColorSpace;
    clonedTexture.minFilter =
      LinearMipmapLinearFilter;
    clonedTexture.anisotropy = 16;
    clonedTexture.needsUpdate = true;

    return clonedTexture;
  }, [loadedTexture]);

  useFrame(() => {
    if (!earthRef.current) {
      return;
    }

    // Rotação da Terra
    earthRef.current.rotation.y += 0.0015;

    // Entrada suave
    const scale = earthRef.current.scale.x;

    if (scale < 1) {
      const nextScale = Math.min(
        scale + 0.004,
        1
      );

      earthRef.current.scale.set(
        nextScale,
        nextScale,
        nextScale
      );
    }
  });

  return (
    <group
      ref={earthRef}
      scale={[0.15, 0.15, 0.15]}
    >
      {/* TERRA */}
      <mesh>
        <sphereGeometry
          args={[2, 128, 128]}
        />

        <meshStandardMaterial
          map={texture}
          roughness={0.9}
          metalness={0}
        />
      </mesh>

      {/* ATMOSFERA */}
      <Atmosphere />
    </group>
  );
}