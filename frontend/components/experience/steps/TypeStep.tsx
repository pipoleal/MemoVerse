"use client";

import FadeIn from "../../animations/FadeIn";

const experienceTypes = [
  {
    id: "dating",
    icon: "❤️",
    title: "Pedido de Namoro",
    description: "Surpreenda quem você ama.",
  },
  {
    id: "marriage",
    icon: "💍",
    title: "Pedido de Casamento",
    description: "Um momento inesquecível.",
  },
  {
    id: "birthday",
    icon: "🎂",
    title: "Aniversário",
    description: "Celebre uma nova fase.",
  },
  {
    id: "monthiversary",
    icon: "👶",
    title: "Mesversário",
    description: "Registre cada mês especial.",
  },
  {
    id: "tribute",
    icon: "👨‍👩‍👧",
    title: "Homenagem",
    description: "Para quem marcou sua vida.",
  },
  {
    id: "custom",
    icon: "✨",
    title: "Personalizado",
    description: "Crie do seu jeito.",
  },
];

type Props = {
  value?: string;
  onChange?: (value: string) => void;
};

export default function TypeStep({
  value,
  onChange,
}: Props) {
  return (
    <FadeIn>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          Etapa 1
        </span>

        <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-5xl font-black text-transparent">
          Qual experiência você deseja criar?
        </h1>

        <p className="mt-5 max-w-2xl text-slate-300">
          Escolha o tipo da experiência que você deseja criar.
        </p>

        <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
          {experienceTypes.map((type) => {
            const selected = value === type.id;

            return (
              <button
                key={type.id}
                type="button"
                onClick={() => onChange?.(type.id)}
                className={`
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
                      : "border-white/10 bg-white/5 hover:border-yellow-400 hover:bg-white/10"
                  }
                `}
              >
                <div className="text-5xl">
                  {type.icon}
                </div>

                <h2 className="mt-6 text-2xl font-bold text-white">
                  {type.title}
                </h2>

                <p className="mt-3 text-slate-400">
                  {type.description}
                </p>
              </button>
            );
          })}
        </div>
      </section>
    </FadeIn>
  );
}