import { getThemeVisual } from "./themeRegistry";
import type { StarData } from "@/components/universe/types";
import type { Draft } from "@/components/dashboard/useDashboardData";

// Hash determinístico (FNV-1a) de uma string para N floats em [0, 1) —
// mesma ideia de "seed -> pseudo-aleatório estável" já usada em
// GalaxyTransition.tsx/experience-view/StarField.tsx (lá com um índice
// numérico como seed; aqui com o UUID do draft, porque é o único dado
// estável que já existe e não depende de nenhuma coluna nova no banco).
// O mesmo draft.id sempre produz os mesmos floats, então a mesma
// experiência sempre cai na mesma posição entre uma visita e outra.
function hashToUnitFloats(seed: string, count: number): number[] {
  const floats: number[] = [];
  let carry = 0x811c9dc5;

  for (let round = 0; round < count; round++) {
    let hash = carry;
    const roundSeed = `${seed}:${round}`;
    for (let i = 0; i < roundSeed.length; i++) {
      hash ^= roundSeed.charCodeAt(i);
      hash = Math.imul(hash, 0x01000193);
    }
    carry = hash;
    floats.push(((hash >>> 0) % 1_000_000) / 1_000_000);
  }

  return floats;
}

// Espalha as estrelas num disco levemente irregular ao redor da origem —
// "meu universo pessoal", não uma grade nem uma linha. Raio/altura ficam
// dentro do alcance visível da câmera padrão da UniverseEngine
// (position [0,0,12], fov 65).
export function draftToStar(draft: Draft): StarData {
  const [angleSeed, radiusSeed, heightSeed, sizeSeed] = hashToUnitFloats(draft.id, 4);
  const visual = getThemeVisual(draft.theme);

  const angle = angleSeed * Math.PI * 2;
  const radius = 2.5 + radiusSeed * 4.5;
  const height = (heightSeed - 0.5) * 2.2;

  return {
    id: draft.id,
    position: [Math.cos(angle) * radius, height, Math.sin(angle) * radius],
    size: 0.6 + sizeSeed * 0.8,
    // Reaproveita o glow já definido por tema em themeRegistry.ts — nenhuma
    // paleta nova. THREE.Color entende "rgba(r,g,b,a)" (ignora o alfa),
    // então o mesmo valor serve tanto de cor do ponto quanto de glow.
    color: visual.glow,
    glow: visual.glow,
    label: draft.title || "Sem título",
    metadata: draft,
  };
}

export function draftsToStars(drafts: Draft[]): StarData[] {
  return drafts.map(draftToStar);
}
