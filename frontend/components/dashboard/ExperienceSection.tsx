"use client";

import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";
import ExperienceCard from "./ExperienceCard";
import type { Draft } from "./useDashboardData";

type ExperienceSectionProps = {
  drafts: Draft[] | null;
  loading: boolean;
  error: boolean;
};

export default function ExperienceSection({ drafts, loading, error }: ExperienceSectionProps) {
  const router = useRouter();

  return (
    <section>
      <h2 className="mb-8 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-3xl font-bold text-transparent">
        Minhas experiências
      </h2>

      {error && <p className="text-slate-400">Não foi possível carregar suas experiências agora.</p>}

      {!error && loading && <p className="text-slate-400">Carregando suas memórias...</p>}

      {!error && !loading && drafts && drafts.length === 0 && (
        <FadeIn>
          <div className="rounded-3xl border border-white/10 bg-white/5 p-12 text-center backdrop-blur-xl">
            <span className="text-4xl">🌌</span>
            <p className="mt-4 text-xl font-semibold text-white">Seu universo ainda está vazio.</p>
            <p className="mt-2 text-slate-400">Crie sua primeira experiência e transforme-a em uma memória eterna.</p>
            <Button className="mt-8 px-8 py-3 text-sm" onClick={() => router.push("/experience/new")}>
              Criar minha primeira experiência
            </Button>
          </div>
        </FadeIn>
      )}

      {!error && !loading && drafts && drafts.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {drafts.map((draft) => (
            <ExperienceCard key={draft.id} draft={draft} />
          ))}
        </div>
      )}
    </section>
  );
}
