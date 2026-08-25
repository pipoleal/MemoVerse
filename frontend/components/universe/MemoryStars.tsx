"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import type { ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";

import type { StarData } from "./types";

type MemoryStarsProps = {
  stars: StarData[];
  // Fase 2 (Minha Galáxia): callbacks/estado de interação, opcionais —
  // omitidos, o comportamento é idêntico ao da Fase 1 (só as estrelas,
  // sem clique nem destaque). Hover é mantido só internamente (não sobe
  // para o consumidor): a única coisa que hover precisa fazer é destacar
  // a estrela, e isso já acontece aqui.
  onSelect?: (star: StarData) => void;
  selectedId?: string | null;
};

// Polimento visual (identidade própria da estrela de memória): sempre
// dourado — NUNCA a cor por tema (star.color), a pedido explícito do
// produto ("memória preciosa"). star.color/glow continuam existindo em
// StarData/galaxyStars.ts (intocado) para um detalhe secundário futuro,
// só não são lidos aqui.
const STAR_GOLD = "#ffd966";
// Tamanho do ponto (px) a ATTENUATION_REFERENCE_DISTANCE de distância da
// câmera — perto/longe disso escala por (referência / distância real),
// nunca um valor fixo gigante. Calibrado visualmente para a câmera padrão
// da UniverseEngine (position [0,0,12]) e o raio de espalhamento das
// estrelas em galaxyStars.ts (2.5–7 ao redor da origem).
const BASE_POINT_SIZE = 22;
const ATTENUATION_REFERENCE_DISTANCE = 12;

// Textura procedural única (canvas 2D, nunca uma imagem externa): núcleo
// branco no centro, halo em várias camadas de gradiente radial e 4 raios
// sutis — tudo em um único sprite branco com alfa gradual (a cor dourada
// entra depois, multiplicada no shader/material). Gerada uma única vez
// (singleton client-only) e reaproveitada tanto pelos pontos quanto pelo
// halo de hover/seleção — nunca recriada por estrela nem por render.
let starTextureSingleton: THREE.CanvasTexture | null = null;

function getStarTexture(): THREE.CanvasTexture {
  if (starTextureSingleton) return starTextureSingleton;

  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    starTextureSingleton = new THREE.CanvasTexture(canvas);
    return starTextureSingleton;
  }

  const cx = size / 2;
  const cy = size / 2;

  // Halo: glow amplo, alfa caindo suavemente até 0 — nada de borda dura.
  const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2);
  halo.addColorStop(0, "rgba(255,255,255,0.85)");
  halo.addColorStop(0.25, "rgba(255,255,255,0.45)");
  halo.addColorStop(0.55, "rgba(255,255,255,0.16)");
  halo.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, size, size);

  // Raios sutis (4 pontas) — discretos, nunca um brilho "explosivo".
  ctx.save();
  ctx.translate(cx, cy);
  const rayLength = size * 0.44;
  for (let i = 0; i < 4; i++) {
    ctx.save();
    ctx.rotate((Math.PI / 2) * i);
    const ray = ctx.createLinearGradient(0, 0, 0, -rayLength);
    ray.addColorStop(0, "rgba(255,255,255,0.45)");
    ray.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = ray;
    ctx.fillRect(-1.1, -rayLength, 2.2, rayLength);
    ctx.restore();
  }
  ctx.restore();

  // Núcleo: pequeno e muito brilhante, por cima de tudo o resto.
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.15);
  core.addColorStop(0, "rgba(255,255,255,1)");
  core.addColorStop(0.6, "rgba(255,255,255,0.9)");
  core.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.15, 0, Math.PI * 2);
  ctx.fill();

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  starTextureSingleton = texture;
  return texture;
}

// Hash determinístico (mesma família de GalaxyTransition.tsx/
// lib/galaxyStars.ts, só que local — nada aqui decide posição/cor, só a
// fase do brilho) para que cada estrela pulse fora de sincronia com as
// outras, mas sempre com a mesma fase entre uma visita e outra.
function phaseFromId(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return (hash % 1000) / 1000 * Math.PI * 2;
}

const VERTEX_SHADER = `
  attribute float aPhase;
  attribute float aSize;
  attribute float aBoost;
  uniform float uTime;
  varying float vGlow;

  void main() {
    float pulse = 0.82 + 0.18 * sin(uTime * 1.1 + aPhase);
    vGlow = pulse * aBoost;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * ${BASE_POINT_SIZE.toFixed(1)} * pulse * aBoost * (${ATTENUATION_REFERENCE_DISTANCE.toFixed(1)} / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAGMENT_SHADER = `
  uniform sampler2D uTexture;
  uniform vec3 uColor;
  varying float vGlow;

  void main() {
    vec4 tex = texture2D(uTexture, gl_PointCoord);
    if (tex.a < 0.02) discard;
    gl_FragColor = vec4(uColor * (0.75 + 0.5 * vGlow), tex.a);
  }
`;

// Uma "estrela de memória" por experiência real, desenhada como um único
// THREE.Points — nunca um <mesh> React por estrela — para não pagar o
// custo de um objeto Three.js por experiência quando a lista crescer
// (mesmo padrão de geometria por BufferAttribute já usado em
// GalaxyTransition.tsx/ShootingStars.tsx). O brilho pulsante com fase
// própria por estrela, e o destaque de hover/seleção, também não criam
// nada por estrela: rodam num shader simples (uTime, um uniform por
// frame) e num único BufferAttribute mutável (aBoost), nunca um loop JS
// por estrela nem um mesh extra por estrela.
//
// Raycasting contra um único THREE.Points funciona nativamente no
// react-three-fiber independente do material usado aqui: o evento de
// ponteiro carrega `index`, o vértice atingido — não é preciso um objeto
// por estrela para saber qual foi clicada (ver UniverseEngine.tsx para o
// threshold do raycaster, intocado nesta mudança).
export default function MemoryStars({ stars, onSelect, selectedId }: MemoryStarsProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const pointsRef = useRef<THREE.Points>(null);

  const texture = useMemo(() => getStarTexture(), []);

  const geometry = useMemo(() => {
    const positions = new Float32Array(stars.length * 3);
    const phases = new Float32Array(stars.length);
    const sizes = new Float32Array(stars.length);
    const boosts = new Float32Array(stars.length).fill(1);

    stars.forEach((star, index) => {
      positions[index * 3] = star.position[0];
      positions[index * 3 + 1] = star.position[1];
      positions[index * 3 + 2] = star.position[2];
      phases[index] = phaseFromId(star.id);
      sizes[index] = star.size;
    });

    const bufferGeometry = new THREE.BufferGeometry();
    bufferGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    bufferGeometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
    bufferGeometry.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    bufferGeometry.setAttribute("aBoost", new THREE.BufferAttribute(boosts, 1));

    return bufferGeometry;
  }, [stars]);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uTexture: { value: texture },
      uColor: { value: new THREE.Color(STAR_GOLD) },
    }),
    [texture]
  );

  // Único uniform atualizado por frame (uTime) — não um loop por estrela;
  // a fase de cada uma já está no BufferAttribute aPhase, lido pelo
  // próprio shader. Muta através do material montado (pointsRef), nunca
  // através do objeto `uniforms` memoizado diretamente.
  useFrame(({ clock }) => {
    const material = pointsRef.current?.material as THREE.ShaderMaterial | undefined;
    if (material) material.uniforms.uTime.value = clock.getElapsedTime();
  });

  // Nunca deixa o cursor "pointer" grudado se o componente desmontar com
  // uma estrela em hover (ex.: troca de rota).
  useEffect(() => {
    return () => {
      document.body.style.cursor = "auto";
    };
  }, []);

  // Reforça a estrela em hover/selecionada (tamanho/brilho) mutando um
  // único BufferAttribute já existente na geometria montada (pointsRef)
  // — nunca reconstruindo a geometria, nunca um mesh extra só para isso.
  // Só roda quando hover/seleção mudam, nunca a cada frame.
  useEffect(() => {
    const attribute = pointsRef.current?.geometry.getAttribute("aBoost") as THREE.BufferAttribute | undefined;
    if (!attribute) return;

    const array = attribute.array as Float32Array;
    array.fill(1);

    const selectedIndex = selectedId ? stars.findIndex((star) => star.id === selectedId) : -1;
    if (hoveredIndex !== null && hoveredIndex !== selectedIndex) {
      array[hoveredIndex] = 1.25;
    }
    if (selectedIndex !== -1) {
      array[selectedIndex] = 1.55;
    }

    attribute.needsUpdate = true;
  }, [hoveredIndex, selectedId, stars]);

  const hoveredStar = hoveredIndex !== null ? (stars[hoveredIndex] ?? null) : null;
  const selectedStar = selectedId ? (stars.find((star) => star.id === selectedId) ?? null) : null;

  function handlePointerMove(event: ThreeEvent<PointerEvent>) {
    event.stopPropagation();
    if (event.index === undefined || event.index === hoveredIndex) return;
    setHoveredIndex(event.index);
    document.body.style.cursor = "pointer";
  }

  function handlePointerOut() {
    setHoveredIndex(null);
    document.body.style.cursor = "auto";
  }

  function handleClick(event: ThreeEvent<MouseEvent>) {
    event.stopPropagation();
    if (event.index === undefined) return;
    const star = stars[event.index];
    if (star) onSelect?.(star);
  }

  return (
    <>
      <points
        ref={pointsRef}
        geometry={geometry}
        onPointerMove={onSelect ? handlePointerMove : undefined}
        onPointerOut={onSelect ? handlePointerOut : undefined}
        onClick={onSelect ? handleClick : undefined}
      >
        <shaderMaterial
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
          vertexShader={VERTEX_SHADER}
          fragmentShader={FRAGMENT_SHADER}
          uniforms={uniforms}
        />
      </points>

      {hoveredStar && hoveredStar.id !== selectedId && (
        <StarHalo position={hoveredStar.position} texture={texture} scale={0.9} opacity={0.4} />
      )}

      {selectedStar && <StarHalo position={selectedStar.position} texture={texture} scale={1.5} opacity={0.55} />}
    </>
  );
}

type StarHaloProps = {
  position: [number, number, number];
  texture: THREE.CanvasTexture;
  scale: number;
  opacity: number;
};

// Único sprite extra por halo ativo (no máximo dois: hover + seleção) —
// não um por estrela da lista. Sprite (não mesh+geometria própria)
// porque já encara a câmera sozinho e reaproveita a mesma textura do
// núcleo/glow das estrelas, só maior e mais opaco.
function StarHalo({ position, texture, scale, opacity }: StarHaloProps) {
  return (
    <sprite position={position} scale={[scale, scale, scale]}>
      <spriteMaterial
        map={texture}
        color={STAR_GOLD}
        transparent
        opacity={opacity}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </sprite>
  );
}
