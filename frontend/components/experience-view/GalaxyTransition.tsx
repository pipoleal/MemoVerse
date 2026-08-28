"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

import { getStarTexture } from "@/lib/starTexture";

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

// Mesma câmera de GalaxyChapter.tsx (position [0,0,12]) — a referência de
// distância do shader abaixo é calibrada para ela, mesmo padrão de
// MemoryStars.tsx (que também fixa sua referência na câmera padrão da
// UniverseEngine). BASE_POINT_SIZE foi calibrado visualmente para
// reproduzir a mesma escala de nuvem de poeira que o THREE.PointsMaterial
// (size=0.016) desenhava antes desta mudança — não é o mesmo sistema de
// unidades do PointsMaterial, só o resultado visual comparável.
const BASE_POINT_SIZE = 4;
const ATTENUATION_REFERENCE_DISTANCE = 12;

// Vertex/fragment shader — mesma família de MemoryStars.tsx (pulso de
// brilho por partícula via uTime+aPhase, tamanho por partícula via aSize,
// texture2D amostrada em gl_PointCoord com discard sob um limiar de alfa
// para nunca deixar o quadrado/retângulo cru do GL_POINTS aparecer). A
// única diferença real: aqui a opacidade GLOBAL da nuvem (uOpacity, que
// sobe/desce por fase em useFrame abaixo) entra multiplicada no alfa final
// — em MemoryStars não existe essa noção de "opacidade da cena toda".
const VERTEX_SHADER = `
  attribute float aPhase;
  attribute float aSize;
  uniform float uTime;
  varying float vGlow;

  void main() {
    float pulse = 0.82 + 0.18 * sin(uTime * 0.6 + aPhase);
    vGlow = pulse;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * ${BASE_POINT_SIZE.toFixed(1)} * pulse * (${ATTENUATION_REFERENCE_DISTANCE.toFixed(1)} / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAGMENT_SHADER = `
  uniform sampler2D uTexture;
  uniform vec3 uColor;
  uniform float uOpacity;
  varying float vGlow;

  void main() {
    vec4 tex = texture2D(uTexture, gl_PointCoord);
    // Limiar bem mais alto que o de MemoryStars.tsx (0.02): partículas
    // aqui têm poucos pixels de lado (nuvem inicial bem compacta), então a
    // GPU amostra a textura já num mip bem reduzido — nesse nível, a média
    // do halo amplo por si só já passa de 0.02 em quase todo o sprite
    // (vira um quadrado sólido, exatamente o bug antigo). Um limiar alto
    // descarta esse halo médio e deixa passar só o núcleo de verdade,
    // preservando o formato redondo mesmo num ponto pequeno.
    if (tex.a < 0.5) discard;
    gl_FragColor = vec4(uColor * (0.7 + 0.5 * vGlow), tex.a * uOpacity);
  }
`;

export default function GalaxyTransition({
  active,
  phase,
}: GalaxyTransitionProps) {
  const pointsRef = useRef<THREE.Points>(null);
  const materialRef =
    useRef<THREE.ShaderMaterial>(null);

  // Mesma textura procedural (halo + raios + núcleo) que Minha Galáxia já
  // usa — singleton compartilhado, nunca uma segunda geração de canvas.
  const starTexture = useMemo(() => getStarTexture(), []);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uTexture: { value: starTexture },
      uColor: { value: new THREE.Color(0xfff2d0) },
      uOpacity: { value: 0 },
    }),
    [starTexture]
  );

  const geometry = useMemo(() => {
    const positions = new Float32Array(
      PARTICLE_COUNT * 3
    );
    // aPhase (fase do brilho pulsante) e aSize (variação de tamanho) —
    // preenchidos NO MESMO loop que já constrói as posições abaixo, nunca
    // um segundo loop por partícula. Sementes deterministas, mesmo estilo
    // de seedA/seedB/seedC já usado neste arquivo para a posição.
    const phases = new Float32Array(PARTICLE_COUNT);
    const sizes = new Float32Array(PARTICLE_COUNT);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const index = i * 3;

      const seedD =
        Math.sin(i * 94.673) *
        43758.5453;
      const seedE =
        Math.sin(i * 27.192) *
        43758.5453;

      phases[i] = Math.abs(seedD % 1) * Math.PI * 2;
      sizes[i] = 0.6 + Math.abs(seedE % 1) * 0.8;

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
    geometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
    geometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));

    return geometry;
  }, []);

  useFrame((state, delta) => {
    if (!pointsRef.current) {
      return;
    }

    const material =
      materialRef.current;

    if (material) {
      material.uniforms.uTime.value = state.clock.elapsedTime;
    }

    /*
     * Antes de começar.
     */
    if (!active) {
      if (material) {
        material.uniforms.uOpacity.value = 0;
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
      material.uniforms.uOpacity.value +=
        (targetOpacity -
          material.uniforms.uOpacity.value) *
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
      <shaderMaterial
        ref={materialRef}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        vertexShader={VERTEX_SHADER}
        fragmentShader={FRAGMENT_SHADER}
        uniforms={uniforms}
      />
    </points>
  );
}