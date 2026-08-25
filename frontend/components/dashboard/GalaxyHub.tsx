"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";
import UniverseEngine from "../universe/UniverseEngine";
import ExperienceCard, { formatDraftDate } from "./ExperienceCard";
import GalaxyCanvasBoundary from "./GalaxyCanvasBoundary";
import { draftsToStars } from "@/lib/galaxyStars";
import { getThemeVisual } from "@/lib/themeRegistry";
import { isWebGLAvailable } from "@/lib/webgl";
import type { Draft } from "./useDashboardData";

type GalaxyHubProps = {
  drafts: Draft[] | null;
  loading: boolean;
  error: boolean;
};

// Fase 2: a mesma galáxia agora tem uma camada 3D (UniverseEngine +
// MemoryStars, Fase 1) acima da lista de ExperienceCard já existente — a
// lista nunca é removida (ver "FALLBACK 2D" no plano): é a via garantida
// de acessar as experiências sem depender de hover/clique no Canvas, sem
// WebGL, ou se a galáxia 3D falhar ao renderizar (ver GalaxyCanvasBoundary).
export default function GalaxyHub({ drafts, loading, error }: GalaxyHubProps) {
  const router = useRouter();
  const publishedDrafts = drafts?.filter((draft) => draft.status === "published") ?? null;

  const [selectedId, setSelectedId] = useState<string | null>(null);
  // Assume suporte até a checagem client-side (useEffect) provar o
  // contrário — evita um flash de "sem WebGL" enquanto ainda não sabemos.
  const [webglSupported, setWebglSupported] = useState(true);

  // isWebGLAvailable() só pode rodar no cliente (usa document/window) —
  // rodar no efeito, corrigindo o estado depois da primeira renderização
  // em vez de num inicializador de useState, é o padrão recomendado pelo
  // próprio React para "valor que só existe no cliente" (evita erro de
  // hidratação; o pior caso vira uma segunda renderização, nunca um
  // crash). Ver https://react.dev/reference/react-dom/client/hydrateRoot#handling-different-client-and-server-content.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setWebglSupported(isWebGLAvailable());
  }, []);

  const stars = useMemo(
    () => (publishedDrafts ? draftsToStars(publishedDrafts) : []),
    [publishedDrafts]
  );

  const draftsById = useMemo(() => {
    const map = new Map<string, Draft>();
    publishedDrafts?.forEach((draft) => map.set(draft.id, draft));
    return map;
  }, [publishedDrafts]);

  const selectedDraft = selectedId ? (draftsById.get(selectedId) ?? null) : null;

  return (
    <section>
      <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">🌌 Minha Galáxia</span>

      <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-4xl font-black text-transparent sm:text-5xl">
        Suas experiências eternizadas
      </h1>

      <p className="mt-5 max-w-2xl text-slate-300">
        Cada experiência que você publicou vira uma estrela aqui — sempre pronta para reviver.
      </p>

      <div className="mt-12">
        {error && <p className="text-slate-400">Não foi possível carregar sua galáxia agora.</p>}

        {!error && loading && <p className="text-slate-400">Carregando sua galáxia...</p>}

        {!error && !loading && publishedDrafts && publishedDrafts.length === 0 && (
          <FadeIn>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-12 text-center backdrop-blur-xl">
              <span className="text-4xl">🌠</span>
              <p className="mt-4 text-xl font-semibold text-white">Sua galáxia ainda não tem estrelas.</p>
              <p className="mt-2 text-slate-400">Publique sua primeira experiência para vê-la brilhar aqui.</p>
              <Button className="mt-8 px-8 py-3 text-sm" onClick={() => router.push("/experience/new")}>
                Criar minha primeira experiência
              </Button>
            </div>
          </FadeIn>
        )}

        {!error && !loading && publishedDrafts && publishedDrafts.length > 0 && (
          <>
            <div className="relative mb-10 h-[55vh] min-h-[420px] overflow-hidden rounded-3xl border border-white/10 bg-black/40 sm:h-[60vh]">
              {webglSupported ? (
                <GalaxyCanvasBoundary fallback={<GalaxyFallbackNotice />}>
                  <UniverseEngine
                    cameraRig
                    memoryStars={stars}
                    selectedStarId={selectedId}
                    onSelectStar={(star) => setSelectedId(star.id)}
                  />
                </GalaxyCanvasBoundary>
              ) : (
                <GalaxyFallbackNotice />
              )}

              {selectedDraft && (
                <SelectedStarPanel
                  draft={selectedDraft}
                  onClose={() => setSelectedId(null)}
                  onOpen={() => router.push(`/e/${selectedDraft.slug}`)}
                />
              )}
            </div>

            <h2 className="mb-5 text-xl font-bold text-white">Todas as suas experiências</h2>

            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {publishedDrafts.map((draft) => (
                <ExperienceCard key={draft.id} draft={draft} />
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

// Sem WebGL, ou se o Canvas falhar em runtime (GalaxyCanvasBoundary) — a
// lista completa abaixo continua disponível de qualquer forma, então isto
// é só uma explicação, nunca um beco sem saída.
function GalaxyFallbackNotice() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <span className="text-3xl">🌠</span>
      <p className="font-semibold text-white">Sua galáxia 3D não carregou neste navegador.</p>
      <p className="max-w-sm text-sm text-slate-400">
        Sem problema — todas as suas experiências continuam na lista logo abaixo.
      </p>
    </div>
  );
}

type SelectedStarPanelProps = {
  draft: Draft;
  onClose: () => void;
  onOpen: () => void;
};

// Painel discreto sobre o Canvas quando uma estrela é selecionada — título,
// tema, data e quantidade de mídias, mais o mesmo destino de navegação que
// o botão "Reviver" de ExperienceCard já usa (/e/[slug], nenhuma rota
// nova).
function SelectedStarPanel({ draft, onClose, onOpen }: SelectedStarPanelProps) {
  const visual = getThemeVisual(draft.theme);

  return (
    <div className="pointer-events-none absolute inset-x-4 bottom-4 sm:inset-x-auto sm:left-4 sm:w-80">
      <div className="pointer-events-auto rounded-2xl border border-white/10 bg-slate-950/90 p-5 shadow-2xl backdrop-blur-xl">
        <div className="flex items-start justify-between gap-3">
          <span className="text-2xl">{visual.icon}</span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-white/10 hover:text-white"
          >
            ✕
          </button>
        </div>

        <h3 className="mt-2 text-lg font-bold text-white">{draft.title || "Sem título"}</h3>

        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-400">
          <span>{visual.name}</span>
          <span className="text-slate-600">·</span>
          <span>{formatDraftDate(draft)}</span>
          <span className="text-slate-600">·</span>
          <span>{draft.media.length} {draft.media.length === 1 ? "memória" : "memórias"}</span>
        </div>

        <Button variant="primary" className="mt-4 w-full px-6 py-3 text-sm" onClick={onOpen}>
          Reviver experiência
        </Button>
      </div>
    </div>
  );
}
