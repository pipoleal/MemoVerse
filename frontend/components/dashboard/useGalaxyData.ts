"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { DashboardData, Draft } from "./useDashboardData";

// Etapa Minha Galáxia (destinatário): a única consumidora deste hook é
// GalaxyPage (app/dashboard/galaxia/page.tsx) — o Dashboard principal
// continua em useDashboardData (owner-only, ver comentário lá). Busca
// GET /experiences/drafts/ (minhas) e GET /experiences/received/
// (guardadas via "Criar minha Galáxia") em paralelo e junta num único
// Draft[], cada item marcado com `relation` — preserva a distinção
// internamente mesmo a Galáxia mostrando as duas listas juntas por
// enquanto (ver GalaxyHub.tsx, que não precisa de nenhuma mudança: mesmo
// shape de Draft, mesmo filtro por status "published").
//
// Deduplicado por id como rede de segurança (nunca deveria colidir — o
// backend nunca cria um ExperienceRecipient do próprio dono, ver
// SaveExperienceToGalaxyView.owner_noop —, mas "meus" sempre vence em caso
// de colisão, por ser a fonte mais específica).
export function useGalaxyData(): DashboardData {
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      api.get<Omit<Draft, "relation">[]>("/experiences/drafts/"),
      api.get<Omit<Draft, "relation">[]>("/experiences/received/"),
    ])
      .then(([ownedResponse, receivedResponse]) => {
        if (cancelled) return;

        const merged = new Map<string, Draft>();
        for (const draft of receivedResponse.data) {
          merged.set(draft.id, { ...draft, relation: "received" });
        }
        for (const draft of ownedResponse.data) {
          merged.set(draft.id, { ...draft, relation: "owner" });
        }

        setDrafts(Array.from(merged.values()));
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { drafts, loading: drafts === null && !error, error };
}
