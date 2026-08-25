"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

type GalaxyPhase =
  | "planet"
  | "particles"
  | "galaxy"
  | "message";

type GalaxyTransitionProps = {
  active: boolean;
  phase: GalaxyPhase;
};

const PARTICLE_COUNT = 8000;

// THREE.PointsMaterial with no `map` renders every point as a hard-edged,
// axis-aligned square (WebGL's raw GL_POINTS rasterization) — that square is
// the visual artifact this fixes. A real radial-gradient alpha texture makes
// each particle a soft round mote instead. 64px is plenty since each point
// only ever covers a handful of screen pixels.
function createDustTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
  const center = size / 2;
  const gradient = ctx.createRadialGradient(center, center, 0, center, center, center);
  gradient.addColorStop(0, "rgba(255,255,255,1)");
  gradient.addColorStop(0.35, "rgba(255,244,214,0.8)");
  gradient.addColorStop(1, "rgba(255,244,214,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export default function GalaxyTransition({
  active,
  phase,
}: GalaxyTransitionProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const materialRef =
    useRef<THREE.PointsMaterial>(null);

  // Generated once (real canvas work, not per-frame) — same lifetime as the
  // component instance, exactly like `geometry` below.
  const dustTexture = useMemo(() => createDustTexture(), []);

  const geometry = useMemo(() => {
    const positions = new Float32Array(
      PARTICLE_COUNT * 3
    );

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const index = i * 3;

      /*
       * Valores determinísticos.
       */
      const seedA =
        Math.sin(i * 12.9898) *
        43758.5453;

      const seedB =
        Math.sin(i * 78.233) *
        43758.5453;

      const seedC =
        Math.sin(i * 45.164) *
        43758.5453;

      const randomA =
        Math.abs(seedA % 1);

      const randomB =
        Math.abs(seedB % 1);

      const randomC =
        Math.abs(seedC % 1);

      /*
       * Nuvem inicial.
       *
       * É essa nuvem que queremos
       * preservar porque ela ficou
       * bonita no seu vídeo.
       *
       * randomA/randomC eram usados de forma
       * linear (uniforme) — isso faz a nuvem
       * terminar num corte duro (mesma
       * quantidade de partículas até a borda,
       * nenhuma depois), que sob blending
       * aditivo com milhares de partículas
       * sobrepostas satura para um bloco
       * branco de cara reta, não uma nuvem
       * suave. Elevar a uma potência > 1
       * concentra a densidade perto do centro
       * e afina gradualmente até a borda — a
       * mesma extensão (raio/altura) de antes,
       * só sem o corte abrupto.
       */
      const radiusFalloff =
        Math.pow(randomA, 2.2);

      const radius =
        0.35 + radiusFalloff * 2.0;

      const angle =
        randomB *
        Math.PI *
        2;

      positions[index] =
        Math.cos(angle) *
        radius;

      const ySign =
        randomC < 0.5 ? -1 : 1;

      const yFalloff =
        Math.pow(
          Math.abs(randomC - 0.5) * 2,
          2.2
        );

      positions[index + 1] =
        ySign * yFalloff * 0.7;

      positions[index + 2] =
        Math.sin(angle) *
        radius;
    }

    const geometry =
      new THREE.BufferGeometry();

    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(
        positions,
        3
      )
    );

    return geometry;
  }, []);

  useFrame((_, delta) => {
    if (!pointsRef.current) {
      return;
    }

    const material =
      materialRef.current;

    /*
     * Antes de começar.
     */
    if (!active) {
      if (material) {
        material.opacity = 0;
      }

      return;
    }

    /*
     * =================================
     * OPACIDADE
     * =================================
     */

    /*
     * Tetos reduzidos (eram 0.85/1/0.75): com
     * milhares de partículas aditivas
     * sobrepostas, opacidade máxima = 1
     * satura a região mais densa para branco
     * sólido — reduzir o teto mantém a nuvem
     * brilhante e visível sem nunca "estourar"
     * para um bloco cheio.
     */
    let targetOpacity = 0;

    if (phase === "particles") {
      targetOpacity = 0.5;
    }

    if (phase === "galaxy") {
      targetOpacity = 0.65;
    }

    if (phase === "message") {
      targetOpacity = 0.45;
    }

    if (material) {
      material.opacity +=
        (targetOpacity -
          material.opacity) *
        Math.min(delta * 2, 1);
    }

    /*
     * =================================
     * VELOCIDADE
     * =================================
     */

    let rotationSpeed = 0;

    if (phase === "particles") {
      rotationSpeed = 0.025;
    }

    if (phase === "galaxy") {
      rotationSpeed = 0.045;
    }

    if (phase === "message") {
      rotationSpeed = 0.012;
    }

    pointsRef.current.rotation.y +=
      delta * rotationSpeed;

    /*
     * =================================
     * PARTÍCULAS
     * =================================
     */

    const positionAttribute =
      pointsRef.current.geometry.getAttribute(
        "position"
      ) as THREE.BufferAttribute;

    const positions =
      positionAttribute.array as Float32Array;

    const time =
      performance.now() * 0.001;

    for (
      let i = 0;
      i < PARTICLE_COUNT;
      i++
    ) {
      const index = i * 3;

      let x = positions[index];
      let y =
        positions[index + 1];
      let z =
        positions[index + 2];

      const radius =
        Math.sqrt(
          x * x +
          z * z
        );

      if (radius < 0.02) {
        continue;
      }

      const angle =
        Math.atan2(z, x);

      /*
       * =================================
       * FASE 1 / 2
       * =================================
       *
       * Movimento orbital suave.
       */
      if (
        phase === "particles"
      ) {
        const speed =
          0.10 /
          Math.max(
            radius,
            0.35
          );

        const nextAngle =
          angle +
          speed *
          delta;

        const targetX =
          Math.cos(
            nextAngle
          ) *
          radius;

        const targetZ =
          Math.sin(
            nextAngle
          ) *
          radius;

        x +=
          (targetX - x) *
          delta *
          2;

        z +=
          (targetZ - z) *
          delta *
          2;
      }

      /*
       * =================================
       * FASE 3 / 4 / 5
       * =================================
       *
       * Começamos a puxar as
       * partículas para uma
       * estrutura espiral.
       */
      if (
        phase === "galaxy" ||
        phase === "message"
      ) {
        /*
         * Quanto mais longe,
         * maior a curvatura.
         */
        const spiralAngle =
          angle +
          radius *
          0.75;

        /*
         * Pequena variação para
         * evitar uma forma perfeita.
         */
        const distortion =
          Math.sin(
            i * 0.37
          ) *
          0.12;

        const targetAngle =
          spiralAngle +
          distortion;

        /*
         * Mantemos a distância
         * relativamente estável.
         */
        const targetRadius =
          radius;

        const targetX =
          Math.cos(
            targetAngle
          ) *
          targetRadius;

        const targetZ =
          Math.sin(
            targetAngle
          ) *
          targetRadius;

        /*
         * Movimento para a
         * nova posição.
         */
        x +=
          (targetX - x) *
          delta *
          1.8;

        z +=
          (targetZ - z) *
          delta *
          1.8;

        /*
         * Achatamento gradual.
         */
        y +=
          -y *
          delta *
          0.35;

        /*
         * Pequena ondulação.
         */
        y +=
          Math.sin(
            time * 0.5 +
            radius +
            i * 0.01
          ) *
          0.002;
      }

      positions[index] = x;
      positions[index + 1] = y;
      positions[index + 2] = z;
    }

    positionAttribute.needsUpdate = true;
  });

  return (
    <points
      ref={pointsRef}
      geometry={geometry}
    >
      <pointsMaterial
        ref={materialRef}
        map={dustTexture}
        color={0xfff2d0}
        size={0.016}
        sizeAttenuation
        transparent
        opacity={0}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}