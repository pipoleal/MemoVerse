"use client";

import { useExperience } from "../context/ExperienceContext";
import FadeIn from "../../animations/FadeIn";

const MAX_CHARACTERS = 3000;

export default function LetterStep() {
  const { experience, updateExperience } = useExperience();

  const characters = experience.letter.length;

  function handleLetterChange(
    event: React.ChangeEvent<HTMLTextAreaElement>
  ) {
    const value = event.target.value;

    if (value.length > MAX_CHARACTERS) {
      return;
    }

    updateExperience({
      letter: value,
    });
  }

  return (
    <FadeIn>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          Etapa 6
        </span>

        <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-5xl font-black text-transparent">
          Escreva sua carta
        </h1>

        <p className="mt-5 max-w-2xl text-slate-300">
          Agora é a hora de colocar em palavras aquilo que você
          realmente quer dizer.
        </p>

        <div className="mt-12 grid gap-8 lg:grid-cols-2">
          {/* Editor */}
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-bold text-white">
                  Sua mensagem
                </h2>

                <p className="mt-1 text-sm text-slate-400">
                  Escreva com calma. Essa mensagem fará parte da
                  experiência.
                </p>
              </div>

              <span
                className={`
                  shrink-0 rounded-full px-3 py-1 text-xs font-semibold
                  ${
                    characters >= MAX_CHARACTERS
                      ? "bg-yellow-400/10 text-yellow-300"
                      : "bg-white/5 text-slate-400"
                  }
                `}
              >
                {characters} / {MAX_CHARACTERS}
              </span>
            </div>

            <textarea
              value={experience.letter}
              onChange={handleLetterChange}
              placeholder="Escreva aqui tudo aquilo que você gostaria que essa pessoa soubesse..."
              rows={16}
              className="
                mt-6
                w-full
                resize-none
                rounded-2xl
                border
                border-white/10
                bg-black/20
                px-5
                py-5
                text-base
                leading-7
                text-white
                outline-none
                placeholder:text-slate-600
                transition-all
                focus:border-yellow-400
                focus:ring-2
                focus:ring-yellow-400/20
              "
            />

            <p className="mt-3 text-xs text-slate-500">
              Você pode escrever até {MAX_CHARACTERS.toLocaleString("pt-BR")}{" "}
              caracteres.
            </p>
          </div>

          {/* Preview */}
          <div className="relative overflow-hidden rounded-3xl border border-yellow-400/20 bg-linear-to-br from-yellow-400/10 via-white/5 to-transparent p-8 backdrop-blur-xl">
            <div className="absolute -right-20 -top-20 h-48 w-48 rounded-full bg-yellow-400/10 blur-3xl" />

            <div className="relative">
              <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
                Prévia
              </span>

              <div className="mt-8 rounded-2xl border border-white/10 bg-black/20 p-7">
                <div className="text-3xl">
                  💌
                </div>

                <h2 className="mt-5 text-2xl font-bold text-white">
                  Uma carta para{" "}
                  {experience.recipient || "alguém especial"}
                </h2>

                <div className="mt-6 min-h-48 whitespace-pre-wrap text-base leading-7 text-slate-300">
                  {experience.letter ? (
                    experience.letter
                  ) : (
                    <span className="text-slate-600">
                      Sua carta aparecerá aqui enquanto você escreve...
                    </span>
                  )}
                </div>
                <div className="mt-8 border-t border-white/10 pt-5">
                <p className="text-sm text-slate-500">
                    Mais uma memória para guardar para sempre. ⭐
                </p>

                <p className="mt-3 text-lg font-semibold text-white">
                    {experience.creator || "Seu nome"} ❤️
                </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </FadeIn>
  );
}