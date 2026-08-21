"use client";

import { useEffect, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Trail } from "@react-three/drei";
import * as THREE from "three";

const STAR_COUNT = 5;

type Trajectory = {
  start: THREE.Vector3;
  end: THREE.Vector3;
  duration: number;
};

// A new random diagonal path each time a star resets — near one edge of the
// visible field, crossing past the camera at [0,0,12] (see GalaxyChapter),
// well inside the depth of the <Stars> field behind it. Only ever called
// from useFrame/useEffect (never during render) — Math.random() there is
// fine, the lint rule only forbids impure calls in the render path itself.
function randomTrajectory(): Trajectory {
  const startX = -40 - Math.random() * 20;
  const startY = 10 + Math.random() * 20;
  const z = -20 - Math.random() * 30;

  const angle = -0.4 - Math.random() * 0.3;
  const distance = 55 + Math.random() * 25;

  return {
    start: new THREE.Vector3(startX, startY, z),
    end: new THREE.Vector3(
      startX + Math.cos(angle) * distance,
      startY + Math.sin(angle) * distance,
      z
    ),
    duration: 0.9 + Math.random() * 0.5,
  };
}

function randomCooldown(): number {
  return 3 + Math.random() * 5;
}

// One shooting star: invisible most of the time, becomes visible for
// `duration` seconds while it travels start -> end, then waits out its own
// random cooldown before picking a fresh trajectory. Each instance runs its
// own independent cycle (via a randomized initial delay, chosen once after
// mount) so the pool never fires in sync.
function ShootingStar() {
  const meshRef = useRef<THREE.Mesh>(null);
  const trajectoryRef = useRef<Trajectory | null>(null);
  const elapsedRef = useRef(0);
  const cooldownRef = useRef(0);
  const readyRef = useRef(false);

  // Randomness deliberately lives here (an effect, after mount) rather than
  // during render — see the react-hooks/purity rule this codebase enforces.
  useEffect(() => {
    trajectoryRef.current = randomTrajectory();
    elapsedRef.current = -Math.random() * 6;
    cooldownRef.current = randomCooldown();
    readyRef.current = true;
  }, []);

  useFrame((_, delta) => {
    const mesh = meshRef.current;
    if (!mesh || !readyRef.current || !trajectoryRef.current) return;

    elapsedRef.current += delta;
    const { start, end, duration } = trajectoryRef.current;

    if (elapsedRef.current < 0) {
      mesh.visible = false;
      return;
    }

    if (elapsedRef.current > duration) {
      if (elapsedRef.current > duration + cooldownRef.current) {
        trajectoryRef.current = randomTrajectory();
        cooldownRef.current = randomCooldown();
        elapsedRef.current = 0;
      }
      mesh.visible = false;
      return;
    }

    mesh.visible = true;
    mesh.position.lerpVectors(start, end, elapsedRef.current / duration);
  });

  return (
    <Trail width={1.2} length={5} color="#ffffff" decay={1.4} attenuation={(width) => width}>
      <mesh ref={meshRef} visible={false}>
        <sphereGeometry args={[0.05, 6, 6]} />
        <meshBasicMaterial color="#ffffff" transparent opacity={0.9} />
      </mesh>
    </Trail>
  );
}

// Ambient, self-contained shooting-star effect for the Galaxy's own
// identity (see GalaxyChapter.tsx) — meant to be rendered inside an
// existing <Canvas>, alongside <Stars>/<CameraRig>, never on its own. A
// fixed-size pool (no randomness needed here — each star randomizes its own
// timing internally, after mount).
export default function ShootingStars() {
  return (
    <>
      {Array.from({ length: STAR_COUNT }, (_, index) => (
        <ShootingStar key={index} />
      ))}
    </>
  );
}
