"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { getThemeVisual } from "@/lib/themeRegistry";
import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";
import ThemeVisual from "./ThemeVisual";
import type { Draft, DraftStatus } from "./useDashboardData";

const STATUS_LABELS: Record<DraftStatus, string> = {
  draft: "Rascunho",
  awaiting_payment: "Aguardando pagamento",
  payment_failed: "Pagamento falhou",
  paid: "Pago",
  published: "Publicada",
};

const STATUS_BADGE_CLASS: Record<DraftStatus, string> = {
  draft: "bg-white/10 text-slate-300",
  awaiting_payment: "bg-blue-400/15 text-blue-300",
  payment_failed: "bg-red-400/15 text-red-300",
  paid: "bg-emerald-400/15 text-emerald-300",
  published: "bg-yellow-400/15 text-yellow-300",
};

// Resume/access action for every status except "published" — a published
// experience is eternized, not editable, so it gets its own set of actions
// (Reviver / Compartilhar / menu) below instead of a single generic button.
// Every target here already exists and works today: CheckoutView already
// resumes checkout from any of these statuses, and /experience/edit/[draftId]
// already loads a draft back into the wizard — this only relabels/wires the
// card into those same routes.
function getDraftAction(status: Exclude<DraftStatus, "published">, id: string): { label: string; href: string } {
  switch (status) {
    case "draft":
      return { label: "Continuar criação", href: `/experience/edit/${id}` };
    case "awaiting_payment":
      return { label: "Continuar pagamento", href: `/checkout/${id}` };
    case "payment_failed":
      return { label: "Tentar pagamento novamente", href: `/checkout/${id}` };
    case "paid":
      return { label: "Publicar experiência", href: `/checkout/${id}` };
  }
}

// Exportado (Fase 2 — Minha Galáxia) para o painel de seleção de estrela
// de GalaxyHub.tsx reaproveitar a mesma formatação de data, em vez de
// duplicá-la.
export function formatDraftDate(draft: Draft) {
  const date = draft.event_date ? new Date(`${draft.event_date}T00:00:00`) : new Date(draft.created_at);
  if (Number.isNaN(date.getTime())) return draft.event_date ?? draft.created_at;
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "long", year: "numeric" }).format(date);
}

export default function ExperienceCard({ draft }: { draft: Draft }) {
  const router = useRouter();
  const [copyFeedback, setCopyFeedback] = useState<"idle" | "copied" | "failed">("idle");
  const [menuOpen, setMenuOpen] = useState(false);

  const visual = getThemeVisual(draft.theme);

  async function copyLink() {
    // window is only ever touched inside this handler (never during
    // render), so it's never reached during SSR — draft.slug alone gates
    // whether the button/menu item is even shown.
    if (!draft.slug) return;
    setMenuOpen(false);
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/e/${draft.slug}`);
      setCopyFeedback("copied");
    } catch {
      setCopyFeedback("failed");
    } finally {
      setTimeout(() => setCopyFeedback("idle"), 2500);
    }
  }

  return (
    <FadeIn>
      <div
        className={`
          group flex flex-col rounded-3xl border border-white/10 bg-white/5 p-6
          backdrop-blur-xl transition-all duration-300
          hover:-translate-y-2 hover:border-white/20
        `}
        onMouseEnter={(event) => (event.currentTarget.style.boxShadow = `0 0 40px 0 ${visual.glow}`)}
        onMouseLeave={(event) => (event.currentTarget.style.boxShadow = "none")}
      >
        <ThemeVisual theme={draft.theme} />

        <div className="mt-5 flex items-start justify-between gap-3">
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_BADGE_CLASS[draft.status]}`}>
            {STATUS_LABELS[draft.status]}
          </span>

          {draft.status === "published" && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                aria-haspopup="true"
                aria-expanded={menuOpen}
                aria-label="Mais ações"
                className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full text-slate-400 transition hover:bg-white/10 hover:text-white"
              >
                ⋯
              </button>

              {menuOpen && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden="true" />
                  <div className="absolute right-0 z-20 mt-2 w-48 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 py-1 shadow-2xl backdrop-blur-xl">
                    <button
                      type="button"
                      onClick={copyLink}
                      className="block w-full px-4 py-3 text-left text-sm text-slate-200 transition hover:bg-white/10"
                    >
                      Copiar link
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setMenuOpen(false);
                        router.push(`/e/${draft.slug}`);
                      }}
                      className="block w-full px-4 py-3 text-left text-sm text-slate-200 transition hover:bg-white/10"
                    >
                      Abrir experiência
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <h2 className="mt-4 text-xl font-bold text-white">{draft.title || "Sem título"}</h2>
        <p className="mt-1 text-slate-400">Para {draft.recipient_name || "—"}</p>

        <div className="mt-4 flex items-center gap-2 text-sm text-slate-400">
          <span>
            {visual.icon} {visual.name}
          </span>
          <span className="text-slate-600">·</span>
          <span>{formatDraftDate(draft)}</span>
        </div>

        <div className="mt-6 flex-1" />

        {draft.status === "published" ? (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              variant="primary"
              className="flex-1 py-3 text-sm"
              onClick={() => router.push(`/e/${draft.slug}`)}
            >
              Reviver
            </Button>
            <Button variant="secondary" className="flex-1 py-3 text-sm" onClick={copyLink}>
              {copyFeedback === "copied" ? "✓ Copiado" : copyFeedback === "failed" ? "Não copiou" : "Compartilhar"}
            </Button>
          </div>
        ) : (
          (() => {
            const action = getDraftAction(draft.status, draft.id);
            return (
              <Button variant="secondary" className="w-full py-3 text-sm" onClick={() => router.push(action.href)}>
                {action.label}
              </Button>
            );
          })()
        )}
      </div>
    </FadeIn>
  );
}
