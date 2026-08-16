"use client";

import { useEffect, useRef, useState } from "react";

import ExperienceViewer from "@/components/experience-view/ExperienceViewer";
import type { Experience } from "@/components/experience/types";
import { fetchPublicExperience, isNotFoundError, toExperience } from "@/lib/publicExperience";

type LoadState =
  | { kind: "loading" }
  | { kind: "not_found" }
  | { kind: "error"; message: string }
  | { kind: "ready"; experience: Experience };

export default function PublicExperienceView({ slug }: { slug: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  // Guards against React StrictMode's dev-only double-invoke of effects —
  // without this, a fresh tab load would fire the request twice.
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    if (hasFetchedRef.current) return;
    hasFetchedRef.current = true;

    let cancelled = false;

    fetchPublicExperience(slug)
      .then((data) => {
        if (cancelled) return;
        setState({ kind: "ready", experience: toExperience(data) });
      })
      .catch((error) => {
        if (cancelled) return;
        if (isNotFoundError(error)) {
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

  return <ExperienceViewer experience={state.experience} />;
}
