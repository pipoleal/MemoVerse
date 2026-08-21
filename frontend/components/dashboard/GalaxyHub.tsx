"use client";

import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";
import ExperienceCard from "./ExperienceCard";
import type { Draft } from "./useDashboardData";

type GalaxyHubProps = {
  drafts: Draft[] | null;
  loading: boolean;
  error: boolean;
};

// V1: a hub of the creator's own published experiences, reusing exactly the
// same ExperienceCard already used on the main Dashboard (it already knows
// how to render a published draft — Reviver/Compartilhar). Deliberately not
// a 3D/navigable galaxy — that's a larger, separate piece of work, out of
// scope here (see the Fase 1 audit).
export default function GalaxyHub({ drafts, loading, error }: GalaxyHubProps) {
  const router = useRouter();
  const publishedDrafts = drafts?.filter((draft) => draft.status === "published") ?? null;

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
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {publishedDrafts.map((draft) => (
              <ExperienceCard key={draft.id} draft={draft} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
