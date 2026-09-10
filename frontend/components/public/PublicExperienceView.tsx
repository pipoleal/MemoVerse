"use client";

import { useEffect, useState } from "react";

import ExperienceViewer from "@/components/experience-view/ExperienceViewer";
import type { Experience } from "@/components/experience/types";
import { fetchPublicExperience, isExpiredError, isNotFoundError, toExperience } from "@/lib/publicExperience";

// Número oficial do WhatsApp de suporte — mesmo valor de
// components/layout/Footer.tsx (WHATSAPP_URL), repetido aqui em vez de
// importado do Footer porque ele não exporta a constante e é um componente
// de layout, não um módulo de configuração; mesmo padrão de duplicação
// pontual já usado para MemoryVersebr@gmail.com em app/sobre e
// app/termos-de-uso.
const WHATSAPP_RENEW_URL =
  "https://wa.me/5512992432849?text=" +
  encodeURIComponent("Oi! Minha experiência no MemoVerse expirou e eu queria renovar o plano.");

type LoadState =
  | { kind: "loading" }
  | { kind: "not_found" }
  | { kind: "expired" }
  | { kind: "error"; message: string }
  | { kind: "ready"; experience: Experience; isOwner: boolean; slug: string };

export default function PublicExperienceView({ slug }: { slug: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    // No mount-guard ref here on purpose: React StrictMode's dev-only
    // double-invoke (mount -> cleanup -> mount again) previously interacted
    // badly with a `hasFetchedRef` guard — the ref survived the simulated
    // remount (blocking the second, real effect run) while `cancelled`
    // below did not (it belongs to the first run's closure), so the first
    // run's own cleanup permanently discarded its own fetch's result and
    // the component was stuck on "loading" forever. `cancelled` alone is
    // the correct/standard fix: StrictMode's extra run in dev issues one
    // extra (harmless, cancelled) request, but every run's own fetch is
    // resolved or discarded consistently by its own closure.
    let cancelled = false;

    fetchPublicExperience(slug)
      .then((data) => {
        if (cancelled) return;
        setState({ kind: "ready", experience: toExperience(data), isOwner: data.viewer_can_manage, slug: data.slug });
      })
      .catch((error) => {
        if (cancelled) return;
        if (isExpiredError(error)) {
          setState({ kind: "expired" });
        } else if (isNotFoundError(error)) {
          setState({ kind: "not_found" });
        } else {
          setState({
            kind: "error",
            message: "Não foi possível carregar esta experiência. Tente novamente em instantes.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (state.kind === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-black text-white">
        <div className="flex flex-col items-center gap-4">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
          <p className="text-slate-300">Carregando experiência...</p>
        </div>
      </main>
    );
  }

  if (state.kind === "not_found") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-black px-6 text-center text-white">
        <span className="text-5xl">🔭</span>
        <h1 className="text-2xl font-bold">Experiência não encontrada</h1>
        <p className="max-w-md text-slate-400">
          Este link pode estar incorreto, ou a experiência ainda não foi publicada.
        </p>
      </main>
    );
  }

  if (state.kind === "expired") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-black px-6 text-center text-white">
        <span className="text-5xl">⏳</span>
        <h1 className="text-2xl font-bold">Essa experiência expirou</h1>
        <p className="max-w-md text-slate-400">
          O plano dessa experiência chegou ao fim e ela não está mais disponível. Fale com a
          gente para renovar e reativar o link.
        </p>
        <a
          href={WHATSAPP_RENEW_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
        >
          Renovar pelo WhatsApp
        </a>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-black px-6 text-center text-white">
        <span className="text-5xl">⚠</span>
        <p className="max-w-md text-slate-300">{state.message}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
        >
          Tentar novamente
        </button>
      </main>
    );
  }

  return <ExperienceViewer experience={state.experience} isOwner={state.isOwner} slug={state.slug} />;
}
