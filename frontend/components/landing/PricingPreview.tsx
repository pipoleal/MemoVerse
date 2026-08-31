"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";
import { fetchActivePlans, formatPlanPrice, planCardTitle, type Plan } from "@/lib/checkout";

// Vitrine informativa dos planos na landing page — NUNCA um ponto de escolha
// de plano. O cliente só escolhe o plano de verdade no checkout, depois de
// já ter construído a experiência (draft anônimo -> claim -> checkout, ver
// frontend/CLAUDE.md), porque o preço final também pode incluir um desconto
// específico daquele e-mail (PlanDiscount, ver admin/discounts). Por isso
// nenhum card aqui tem um botão "Escolher" próprio — um único CTA no fim da
// seção sempre leva para /experience/new, igual ao resto da landing.
type LoadState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; plans: Plan[] };

export default function PricingPreview() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetchActivePlans()
      .then((plans) => {
        if (cancelled) return;
        setState({ kind: "ready", plans });
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
    <section id="planos" className="px-6 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl">
        <FadeIn>
          <div className="mx-auto max-w-xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-yellow-400">Planos</p>
            <h2 className="mt-4 text-3xl font-black text-white sm:text-4xl">
              Escolha por quanto tempo sua memória vai brilhar
            </h2>
            <p className="mt-4 text-slate-400">Sem mensalidade. Você paga uma vez, na hora de publicar.</p>
          </div>
        </FadeIn>

        {state.kind === "loading" && (
          <div className="mt-16 flex justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
          </div>
        )}

        {state.kind === "ready" && (
          <>
            <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {state.plans.map((plan, index) => {
                const isGalaxy = plan.features.galaxy_live_enabled;
                return (
                  <FadeIn key={plan.code} delay={index * 0.08}>
                    <div
                      className={`flex h-full flex-col rounded-3xl border p-6 backdrop-blur-xl transition-all duration-300 ${
                        isGalaxy
                          ? "border-yellow-400/40 bg-linear-to-br from-yellow-400/10 via-white/5 to-purple-500/10"
                          : "border-white/10 bg-white/5"
                      }`}
                    >
                      {isGalaxy && (
                        <span className="mb-3 inline-block w-fit rounded-full bg-yellow-400/15 px-3 py-1 text-xs font-bold tracking-wide text-yellow-300">
                          ✨ MAIS COMPLETO
                        </span>
                      )}
                      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">
                        {planCardTitle(plan.name)}
                      </p>
                      <p className="mt-2 text-3xl font-black text-white">{formatPlanPrice(plan.price, plan.currency)}</p>
                      <ul className="mt-5 flex-grow space-y-2 text-sm text-slate-300">
                        {plan.features.highlights.map((item) => (
                          <li key={item} className="flex items-start gap-2">
                            <span className="mt-0.5 text-yellow-400">✓</span>
                            {item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </FadeIn>
                );
              })}
            </div>

            <FadeIn delay={0.2}>
              <div className="mt-12 flex flex-col items-center gap-3">
                <Button variant="primary" onClick={() => router.push("/experience/new")}>
                  ⭐ Criar minha experiência
                </Button>
                <p className="text-xs text-slate-500">
                  Comece de graça — você escolhe o plano só na hora de publicar.
                </p>
              </div>
            </FadeIn>
          </>
        )}
      </div>
    </section>
  );
}
