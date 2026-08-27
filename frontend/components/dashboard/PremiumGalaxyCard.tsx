"use client";

import { useRouter } from "next/navigation";

// Etapa Galáxia Viva: graduou de "só apresenta o conceito, nada clicável"
// pra navegação real — /dashboard/galaxia-viva já existe e decide sozinha
// o que mostrar (tela cheia se o usuário tiver ao menos uma experiência
// com o entitlement galaxy_live_enabled, upsell se não tiver — ver
// GalaxiaVivaView.tsx). Este card nunca checa o entitlement antes de
// navegar, mesmo padrão do card "Minha Galáxia" ao lado (HeroActions.tsx):
// o link de conta é sempre o mesmo, é o destino que decide o conteúdo.
const BENEFITS = [
  "Uma galáxia viva, com animações e efeitos exclusivos para suas memórias",
  "Destaques visuais especiais para experiências Premium",
  "Novos recursos, primeiro para quem tiver a Galáxia Viva",
];

export default function PremiumGalaxyCard() {
  const router = useRouter();

  return (
    <div
      className="
        flex flex-col rounded-3xl border border-yellow-400/25
        bg-linear-to-br from-yellow-400/10 via-white/5 to-purple-500/10
        p-8 backdrop-blur-xl transition-all duration-300
        hover:-translate-y-1 hover:border-yellow-400/50
        hover:shadow-[0_0_50px_rgba(250,204,21,.18)]
      "
    >
      <div className="flex items-center justify-between">
        <span className="text-4xl">✨</span>
        <span className="rounded-full bg-yellow-400/15 px-3 py-1 text-xs font-bold tracking-wide text-yellow-300">
          PREMIUM
        </span>
      </div>

      <h3 className="mt-6 text-2xl font-bold text-white">Galáxia Viva</h3>

      <p className="mt-3 text-slate-300">
        Recursos exclusivos que tornam suas memórias ainda mais incríveis.
      </p>

      <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-300">
        {BENEFITS.map((benefit) => (
          <li key={benefit} className="flex gap-2">
            <span className="text-yellow-400">✦</span>
            {benefit}
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={() => router.push("/dashboard/galaxia-viva")}
        className="mt-6 w-full cursor-pointer rounded-full border border-yellow-400/40 bg-yellow-400/10 py-3 text-sm font-semibold text-yellow-300 transition hover:bg-yellow-400/20"
      >
        Explorar Galáxia Viva
      </button>
    </div>
  );
}
