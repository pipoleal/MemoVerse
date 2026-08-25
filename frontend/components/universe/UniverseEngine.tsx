"use client";

import type { ReactNode } from "react";
import { Canvas } from "@react-three/fiber";

import Scene from "./Scene";
import CameraRig from "./CameraRig";
import ShootingStars from "./ShootingStars";
import MemoryStars from "./MemoryStars";
import type { StarData } from "./types";

// Base 3D reutilizável por trás de Universe.tsx (fundo decorativo, sem
// props) e, a partir da Fase 2, de Minha Galáxia/Galáxia Viva. Composta só
// a partir do que já existia — Scene (fundo de estrelas), CameraRig e
// ShootingStars nunca tiveram sua lógica interna copiada, só passaram a
// ser montados condicionalmente aqui além de onde já eram usados
// (GalaxyChapter.tsx, intocado por esta mudança).
//
// Todo prop tem um default que reproduz exatamente o Canvas que
// Universe.tsx já montava antes desta extração: nenhum consumidor
// existente (landing/login/register/dashboard) passa props hoje, então
// `<UniverseEngine />` sem argumentos precisa continuar pixel a pixel
// igual ao que "Canvas + Scene" já renderizava.
export type UniverseEngineProps = {
  cameraPosition?: [number, number, number];
  cameraFov?: number;
  // Movimento ambiente de câmera — desligado por padrão porque nenhum dos
  // consumidores decorativos atuais tem esse movimento hoje; ligado só
  // onde for pedido (Galáxia).
  cameraRig?: boolean;
  // Estrelas cadentes ambientais — hoje só existem dentro do Canvas
  // próprio de GalaxyChapter.tsx; aqui viram opcionais para quem quiser o
  // mesmo efeito sem duplicar ShootingStars.tsx.
  shootingStars?: boolean;
  // Estrelas de memória (Fase 2+) — cada uma representa uma experiência
  // real. Omitido/vazio não renderiza a camada extra, então o fundo
  // decorativo atual não muda.
  memoryStars?: StarData[];
  // Fase 2: clique numa estrela de memória e id da estrela selecionada
  // (controlado pelo consumidor, ex. GalaxyHub.tsx) — ambos opcionais,
  // sem efeito nenhum se memoryStars não for passado.
  onSelectStar?: (star: StarData) => void;
  selectedStarId?: string | null;
  // Ponto de composição reservado para nebulosa/efeitos (Fases 4/5) —
  // nada é renderizado aqui ainda nesta fase.
  children?: ReactNode;
  // Limite de device pixel ratio — omitido por padrão (Canvas usa seu
  // próprio default, igual a hoje); só passar quando um consumidor
  // precisar reduzir custo em mobile.
  dpr?: number | [number, number];
};

const DEFAULT_CAMERA_POSITION: [number, number, number] = [0, 0, 12];
const DEFAULT_CAMERA_FOV = 65;

// Threshold do raycaster para THREE.Points — só afeta como um clique
// "acerta" uma estrela dentro de MemoryStars (ver ali); não desenha nada
// e não tem custo quando memoryStars está vazio/ausente, então é seguro
// deixar sempre configurado, mesmo para os consumidores decorativos.
const POINTS_RAYCASTER_THRESHOLD = 0.4;

export default function UniverseEngine({
  cameraPosition = DEFAULT_CAMERA_POSITION,
  cameraFov = DEFAULT_CAMERA_FOV,
  cameraRig = false,
  shootingStars = false,
  memoryStars,
  onSelectStar,
  selectedStarId,
  children,
  dpr,
}: UniverseEngineProps) {
  return (
    <Canvas
      camera={{ position: cameraPosition, fov: cameraFov }}
      dpr={dpr}
      raycaster={{
        params: {
          Mesh: {},
          Line: { threshold: 1 },
          LOD: {},
          Points: { threshold: POINTS_RAYCASTER_THRESHOLD },
          Sprite: {},
        },
      }}
    >
      <Scene />
      {cameraRig && <CameraRig />}
      {shootingStars && <ShootingStars />}
      {memoryStars && memoryStars.length > 0 && (
        <MemoryStars stars={memoryStars} onSelect={onSelectStar} selectedId={selectedStarId} />
      )}
      {children}
    </Canvas>
  );
}
