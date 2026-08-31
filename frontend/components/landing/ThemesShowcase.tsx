"use client";

import { useEffect, useState } from "react";

import { cormorant } from "@/lib/fonts";
import FadeIn from "../animations/FadeIn";
import { fetchActiveThemes, type ActiveTheme } from "@/lib/themes";
import { getThemeVisual } from "@/lib/themeRegistry";

// Mesmo padrão de carregamento de components/experience/steps/StyleStep.tsx:
// GET /api/experiences/themes/ é a única fonte de quais temas existem e seu
// nome — getThemeVisual() (frontend) só resolve como cada código é
// desenhado (ícone/gradiente). Aqui é só uma vitrine, sem seleção.
type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; themes: ActiveTheme[] };

export default function ThemesShowcase() {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetchActiveThemes()
      .then((themes) => {
        if (cancelled) return;
        setState({ kind: "ready", themes });
      })
      .catch(() => {
        if (cancelled) return;
        setState({ kind: "error" });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "error") return null;

  return (
    <section id="temas" className="px-6 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl">
        <FadeIn>
          <div className="mx-auto max-w-xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-yellow-400">Temas visuais</p>
            <h2 className={`${cormorant.className} mt-4 text-3xl italic text-white sm:text-4xl`}>Diversos estilos</h2>
            <p className="mt-4 text-slate-400">
              Escolha um tema especial que combina com a história que você quer contar.
            </p>
          </div>
        </FadeIn>

        {state.kind === "loading" && (
          <div className="mt-16 flex justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
          </div>
        )}

        {state.kind === "ready" && (
          <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {state.themes.map((theme, index) => {
              const visual = getThemeVisual(theme.code);
              return (
                <FadeIn key={theme.code} delay={index * 0.06}>
                  <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 transition-all duration-300 hover:-translate-y-1.5 hover:border-white/20">
                    <div className={`flex h-32 items-end p-5 ${visual.gradient}`}>
                      <span className="text-4xl">{visual.icon}</span>
                    </div>
                    <div className="p-5">
                      <p className="font-bold text-white">{theme.name}</p>
                      <p className="mt-1 text-sm text-slate-400">{visual.description}</p>
                    </div>
                  </div>
                </FadeIn>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
