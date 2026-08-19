"use client";

import { useState } from "react";

// Presents the Galáxia Viva concept only — no checkout, no plan check
// against the backend (User has no premium field today), no navigation.
// "Conhecer" just expands a short benefits list in place; there is
// deliberately nothing to click through to yet.
const BENEFITS = [
  "Uma galáxia viva, com animações e efeitos exclusivos para suas memórias",
  "Destaques visuais especiais para experiências Premium",
  "Novos recursos, primeiro para quem tiver a Galáxia Viva",
];

export default function PremiumGalaxyCard() {
  const [expanded, setExpanded] = useState(false);

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

      <p className="mt-3 flex-1 text-slate-300">
        Recursos exclusivos que tornam suas memórias ainda mais incríveis.
      </p>

      {expanded && (
        <ul className="mt-5 space-y-2 text-sm text-slate-300">
          {BENEFITS.map((benefit) => (
            <li key={benefit} className="flex gap-2">
              <span className="text-yellow-400">✦</span>
              {benefit}
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="mt-6 w-full cursor-pointer rounded-full border border-yellow-400/40 bg-yellow-400/10 py-3 text-sm font-semibold text-yellow-300 transition hover:bg-yellow-400/20"
      >
        {expanded ? "Ver menos" : "Conhecer"}
      </button>
    </div>
  );
}
