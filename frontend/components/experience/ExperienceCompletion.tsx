"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useExperience } from "./context/ExperienceContext";
import { savePendingExperience } from "@/lib/pendingExperience";
import { logEvent } from "@/lib/analytics";
import { fetchActivePlans, formatPlanPrice, type Plan } from "@/lib/checkout";

type PriceState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; plans: Plan[] };

// Correção pós-investigação de conversão: esta tela ANTES dizia "Sua
// galáxia está pronta" + "Crie sua conta para guardar esta experiência e
// continuar" — nada nela dizia que publicar exige escolher e pagar um
// plano. Os 2 primeiros cadastros reais em produção pararam exatamente
// aqui: criaram conta e nunca voltaram, porque a mensagem dava a entender
// que o trabalho já estava concluído. A cópia abaixo deixa
// "criar ≠ publicar" explícito e mostra o preço real (nunca hardcoded —
// sempre o catálogo de GET /payments/plans/, o mesmo usado pelo checkout e
// pela landing) antes do usuário decidir criar a conta.
export default function ExperienceCompletion() {
  const router = useRouter();
  const { experience } = useExperience();
  const [priceState, setPriceState] = useState<PriceState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetchActivePlans()
      .then((plans) => {
        if (cancelled) return;
        setPriceState({ kind: "ready", plans });
        if (plans.length > 0) logEvent("pricing_viewed");
      })
      .catch(() => {
        if (cancelled) return;
        setPriceState({ kind: "error" });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  function continueTo(path: "/register" | "/login") {
    savePendingExperience(experience);
    router.push(path);
  }

  const cheapestPrice =
    priceState.kind === "ready" && priceState.plans.length > 0
      ? priceState.plans.reduce((min, plan) => (Number(plan.price) < Number(min.price) ? plan : min))
      : null;

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#040612] px-6 text-center text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(217,180,75,0.18),transparent_40%)]" />
      <div className="relative w-full max-w-xl rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-xl sm:p-12">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-300">MemoVerse</p>
        <h1 className="mt-5 text-4xl font-semibold tracking-tight sm:text-5xl">✨ Sua galáxia está quase pronta</h1>
        <p className="mt-5 text-base leading-relaxed text-slate-300 sm:text-lg">
          Você criou o universo das suas memórias. Agora salve sua experiência, escolha seu plano e publique sua
          galáxia para receber seu link personalizado.
        </p>

        {cheapestPrice && (
          <p className="mt-6 text-sm font-semibold uppercase tracking-[0.2em] text-yellow-300">
            A partir de {formatPlanPrice(cheapestPrice.price, cheapestPrice.currency)}
          </p>
        )}

        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button type="button" onClick={() => continueTo("/register")} className="rounded-full bg-yellow-300 px-6 py-3 font-semibold text-slate-950 transition hover:bg-yellow-200">Continuar e criar minha conta</button>
          <button type="button" onClick={() => continueTo("/login")} className="rounded-full border border-white/20 px-6 py-3 font-semibold text-white transition hover:bg-white/10">Já tenho uma conta</button>
        </div>
      </div>
    </section>
  );
}
