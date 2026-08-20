"use client";

import { useEffect, useState } from "react";

import FadeIn from "../../animations/FadeIn";
import { useExperience } from "../context/ExperienceContext";
import { fetchActiveThemes, type ActiveTheme } from "@/lib/themes";
import { getThemeVisual } from "@/lib/themeRegistry";

// Which themes exist, their name and order come only from
// GET /api/experiences/themes/ (backend) — this step never hardcodes a
// second catalog. getThemeVisual() (frontend registry) only supplies how
// each code is drawn (icon, description, palette) — never what exists.
type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; themes: ActiveTheme[] };

export default function StyleStep() {
  const { experience, updateExperience } = useExperience();
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

  return (
    <FadeIn>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          Etapa 2
        </span>

        <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-5xl font-black text-transparent">
          Escolha um estilo
        </h1>

        <p className="mt-5 max-w-2xl text-slate-300">
          Escolha a atmosfera que melhor combina com a história que você
          deseja contar.
        </p>

        {state.kind === "loading" && (
          <div className="mt-12 flex items-center gap-3 text-slate-400">
            <div className="h-6 w-6 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
            Carregando temas...
          </div>
        )}

        {state.kind === "error" && (
          <div className="mt-12 rounded-3xl border border-red-400/30 bg-red-400/10 p-6 text-red-200">
            Não foi possível carregar os temas disponíveis. Tente novamente em instantes.
          </div>
        )}

        {state.kind === "ready" && (
          <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {state.themes.map((theme) => {
              const visual = getThemeVisual(theme.code);
              const selected = experience.theme === theme.code;

              return (
                <button
                  key={theme.code}
                  type="button"
                  onClick={() =>
                    updateExperience({
                      theme: theme.code,
                    })
                  }
                  className={`
                    group
                    rounded-3xl
                    border
                    p-8
                    text-left
                    backdrop-blur-xl
                    transition-all
                    duration-300
                    ${
                      selected
                        ? "border-yellow-400 bg-yellow-400/10 shadow-[0_0_40px_rgba(250,204,21,.25)]"
                        : "border-white/10 bg-white/5 hover:-translate-y-1 hover:border-yellow-400 hover:bg-white/10 hover:shadow-[0_0_40px_rgba(250,204,21,.15)]"
                    }
                  `}
                >
                  <div className="text-5xl transition-transform duration-300 group-hover:scale-110">
                    {visual.icon}
                  </div>

                  <h2 className="mt-6 text-2xl font-bold text-white">
                    {theme.name}
                  </h2>

                  <p className="mt-3 text-slate-400">
                    {visual.description}
                  </p>

                  {selected && (
                    <div className="mt-6 flex items-center gap-2 text-sm font-semibold text-yellow-400">
                      <span>✓</span>
                      <span>Selecionado</span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </section>
    </FadeIn>
  );
}
