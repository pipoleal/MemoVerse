"use client";

import FadeIn from "../../animations/FadeIn";
import { useExperience } from "../context/ExperienceContext";

const styles = [
  {
    id: "universe",
    icon: "🌌",
    title: "Universo",
    description: "Uma experiência cercada por estrelas e memórias.",
  },
  {
    id: "cinema",
    icon: "🎬",
    title: "Cinema",
    description: "Transforme sua história em uma experiência cinematográfica.",
  },
  {
    id: "beach",
    icon: "🌊",
    title: "Praia",
    description: "Uma atmosfera leve, romântica e cheia de lembranças.",
  },
  {
    id: "flowers",
    icon: "🌸",
    title: "Flores",
    description: "Uma experiência delicada para histórias especiais.",
  },
  {
    id: "night",
    icon: "🌙",
    title: "Noite",
    description: "Uma atmosfera elegante para momentos inesquecíveis.",
  },
  {
    id: "minimal",
    icon: "🤍",
    title: "Minimalista",
    description: "Uma experiência simples, elegante e emocional.",
  },
];

export default function StyleStep() {
  const { experience, updateExperience } = useExperience();

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

        <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {styles.map((style) => {
            const selected = experience.theme === style.id;

            return (
              <button
                key={style.id}
                type="button"
                onClick={() =>
                  updateExperience({
                    theme: style.id,
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
                  {style.icon}
                </div>

                <h2 className="mt-6 text-2xl font-bold text-white">
                  {style.title}
                </h2>

                <p className="mt-3 text-slate-400">
                  {style.description}
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
      </section>
    </FadeIn>
  );
}