"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import Button from "../ui/Button";
import DashboardShell from "./DashboardShell";
import GalaxiaViva from "../universe/GalaxiaViva";
import GalaxiaVivaIntro from "./GalaxiaVivaIntro";
import { useGalaxyData } from "./useGalaxyData";
import { formatDraftDate } from "./ExperienceCard";
import { getThemeVisual } from "@/lib/themeRegistry";
import type { Draft } from "./useDashboardData";

// Meia-noite local do event_date — mesma convenção já usada em
// ExperienceCard.tsx (formatDraftDate) e combinada explicitamente com o
// produto pra GalaxiaViva.tsx: sem hora real do evento guardada no banco
// (event_date é DateField), meia-noite local é o instante estável e
// determinístico que qualquer visitante (dono ou destinatário) calcula
// igual, em qualquer fuso.
function sinceFromEventDate(draft: Draft): Date {
  return new Date(`${draft.event_date}T00:00:00`);
}

// Etapa Galáxia Viva: elegibilidade é por EXPERIÊNCIA paga
// (draft.galaxy_live_enabled, vindo de verdade da API — ver
// apps.experiences.models.ExperienceDraft.get_galaxy_live_enabled), nunca
// por conta. Reaproveita useGalaxyData tal como está (já junta dono +
// recebidas, já devolve esse campo cru do backend) — filtra aqui, sem
// nenhuma mudança no hook.
function isEligible(draft: Draft): boolean {
  return draft.status === "published" && draft.galaxy_live_enabled && Boolean(draft.event_date);
}

export default function GalaxiaVivaView() {
  const router = useRouter();
  const { drafts, loading, error } = useGalaxyData();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // PREVIEW/DEV: introdução em vídeo, um overlay por cima do conteúdo (que
  // já está montado por baixo desde o início — ver o JSX abaixo) — some com
  // um fade, nunca gate o conteúdo. Ver GalaxiaVivaIntro.tsx.
  const [showIntro, setShowIntro] = useState(true);
  // Sobrescreve galaxy_live_music_url localmente após salvar pelo mini-
  // formulário (ver saveMusicUrl abaixo) — evita esperar um refetch de
  // useGalaxyData só pra refletir o que acabamos de confirmar que o
  // backend já salvou. Por draft id, nunca um valor solto — troca de
  // experiência selecionada (ExperiencePicker) nunca vaza a música de outra.
  const [musicOverrides, setMusicOverrides] = useState<Record<string, string>>({});

  const eligible = useMemo(() => drafts?.filter(isEligible) ?? null, [drafts]);
  const selected = selectedId ? (eligible?.find((draft) => draft.id === selectedId) ?? null) : (eligible?.[0] ?? null);

  // PATCH direto no draft — mesmo endpoint/serializer que o wizard já usa
  // (ExperienceDraftSerializer.validate_galaxy_live_music_url já valida no
  // backend), só que a partir da própria tela da Galáxia Viva. Só o dono
  // pode chamar isto de verdade (ver o `selected.relation === "owner"` que
  // condiciona o botão em GalaxiaViva abaixo) — para um "received", a API
  // recusaria de qualquer forma (get_owned_draft_or_404).
  async function saveMusicUrl(url: string) {
    if (!selected) return;
    await api.patch(`/experiences/drafts/${selected.id}/`, { galaxy_live_music_url: url });
    setMusicOverrides((previous) => ({ ...previous, [selected.id]: url }));
  }

  return (
    <DashboardShell>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">✨ Galáxia Viva</span>

        <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-4xl font-black text-transparent sm:text-5xl">
          Cada dia, uma nova estrela
        </h1>

        <p className="mt-5 max-w-2xl text-slate-300">
          Um contador ao vivo do tempo vivido — e uma estrela nova nascendo a cada dia que passa, para sempre.
        </p>

        <div className="mt-12">
          {error && <p className="text-slate-400">Não foi possível carregar sua Galáxia Viva agora.</p>}

          {!error && loading && <p className="text-slate-400">Carregando...</p>}

          {!error && !loading && eligible && eligible.length === 0 && <EmptyState />}

          {!error && !loading && eligible && eligible.length > 0 && selected && (
            <>
              {eligible.length > 1 && (
                <ExperiencePicker eligible={eligible} selectedId={selected.id} onSelect={setSelectedId} />
              )}

              <div className="h-[70vh] min-h-[560px] w-full">
                <GalaxiaViva
                  since={sinceFromEventDate(selected)}
                  musicUrl={musicOverrides[selected.id] ?? selected.galaxy_live_music_url ?? undefined}
                  onSaveMusicUrl={selected.relation === "owner" ? saveMusicUrl : undefined}
                />
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  className="px-6 py-3 text-sm"
                  onClick={() => router.push(`/e/${selected.slug}`)}
                >
                  Ver experiência completa
                </Button>
              </div>

              {showIntro && <GalaxiaVivaIntro onFinish={() => setShowIntro(false)} />}
            </>
          )}
        </div>
      </section>
    </DashboardShell>
  );
}

// Nenhuma experiência elegível ainda — nunca um beco sem saída: "Galáxia
// Viva" é benefício do plano lifetime_galaxy (ver
// apps.payments.migrations.0005_seed_commercial_plans), então o único
// caminho real hoje é criar uma experiência nova e escolher esse plano no
// checkout — não existe (ainda) um fluxo de upgrade de uma experiência já
// paga com outro plano.
function EmptyState() {
  const router = useRouter();

  return (
    <div className="rounded-3xl border border-yellow-400/25 bg-linear-to-br from-yellow-400/10 via-white/5 to-purple-500/10 p-12 text-center backdrop-blur-xl">
      <span className="text-4xl">✨</span>
      <p className="mt-4 text-xl font-semibold text-white">Você ainda não tem uma Galáxia Viva.</p>
      <p className="mx-auto mt-2 max-w-md text-slate-400">
        Esse contador ao vivo, com uma estrela nascendo a cada dia, é exclusivo das experiências no plano Galáxia
        Viva. Crie uma experiência e escolha esse plano no checkout para desbloquear.
      </p>
      <Button className="mt-8 px-8 py-3 text-sm" onClick={() => router.push("/experience/new")}>
        Criar experiência
      </Button>
    </div>
  );
}

type ExperiencePickerProps = {
  eligible: Draft[];
  selectedId: string;
  onSelect: (id: string) => void;
};

// Só aparece quando existe mais de uma experiência elegível (caso comum:
// exatamente uma, e este componente nem monta) — lista curta pra trocar
// qual Galáxia Viva está em tela. Ícone pequeno próprio (não ThemeVisual —
// esse é fixo em h-32, feito pro card grande de ExperienceCard, não caberia
// aqui) na mesma paleta por tema de themeRegistry.ts.
function ExperiencePicker({ eligible, selectedId, onSelect }: ExperiencePickerProps) {
  return (
    <div className="mb-6 flex gap-3 overflow-x-auto pb-2">
      {eligible.map((draft) => {
        const visual = getThemeVisual(draft.theme);
        return (
          <button
            key={draft.id}
            type="button"
            onClick={() => onSelect(draft.id)}
            className={`flex shrink-0 items-center gap-3 rounded-2xl border p-2 pr-4 text-left transition-colors ${
              draft.id === selectedId
                ? "border-yellow-400/60 bg-yellow-400/10"
                : "border-white/10 bg-white/5 hover:border-white/20"
            }`}
          >
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl text-lg ${visual.gradient}`}>
              {visual.icon}
            </div>
            <div>
              <p className="text-sm font-semibold text-white">{draft.title || "Sem título"}</p>
              <p className="text-xs text-slate-400">{formatDraftDate(draft)}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
