"use client";

import { useEffect, useMemo, useState } from "react";

import { getThemeVisual } from "@/lib/themeRegistry";

import ThemeGlyph from "../theme/ThemeGlyph";

type LetterChapterProps = {
  recipient: string;
  creator: string;
  letter: string;
  theme: string;
  eventDate: string;
  // Segunda pergunta contextual do wizard (ver
  // components/experience/informationStepConfig.ts) — mesmo texto livre do
  // usuário, nunca resumido/reescrito. Opcional porque "custom" não tem essa
  // pergunta e drafts antigos podem não ter respondido; "" e undefined se
  // comportam igual (bloco simplesmente não renderiza).
  contextAnswer?: string;
  // A própria pergunta que o usuário respondeu (o `label` do campo
  // contextAnswer em informationStepConfig.ts para o tipo desta
  // experiência) — resolvida pelo chamador (ExperienceViewer), nunca aqui:
  // este componente não sabe nem precisa saber o que é experience.type.
  // undefined cai num rótulo genérico abaixo.
  contextQuestion?: string;
  onComplete: () => void;
};

function formatEventDate(eventDate: string) {
  if (!eventDate) {
    return null;
  }

  const date = new Date(`${eventDate}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return eventDate;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(date);
}

// Última linha curta da carta ("Te amo.", "Com amor, sempre") vira o
// fechamento em destaque do layout, em itálico na cor do tema. Cartas sem
// uma linha assim ficam exatamente como foram escritas.
function splitClosing(letter: string) {
  const lines = letter.trimEnd().split("\n");
  const last = lines[lines.length - 1]?.trim() ?? "";
  const body = lines.slice(0, -1).join("\n").trimEnd();

  if (body && last.length > 0 && last.length <= 40) {
    return { body, closing: last };
  }

  return { body: letter.trimEnd(), closing: null };
}

export default function LetterChapter({
  recipient,
  creator,
  letter,
  theme,
  eventDate,
  contextAnswer,
  contextQuestion,
  onComplete,
}: LetterChapterProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [showContinue, setShowContinue] = useState(false);

  const tokens = useMemo(
    () => getThemeVisual(theme).experience,
    [theme]
  );

  const { body, closing } = useMemo(() => splitClosing(letter), [letter]);

  const formattedEventDate = useMemo(
    () => formatEventDate(eventDate),
    [eventDate]
  );

  useEffect(() => {
    const enterTimer = setTimeout(() => {
      setIsVisible(true);
    }, 180);

    const continueTimer = setTimeout(() => {
      setShowContinue(true);
    }, 1580);

    return () => {
      clearTimeout(enterTimer);
      clearTimeout(continueTimer);
    };
  }, []);

  return (
    // Sem scroll interno (pedido explícito): esta section não é
    // `absolute inset-0` — é um bloco normal (`relative min-h-screen`) que
    // cresce com o conteúdo, deixando quem rola ser a PÁGINA (body), nunca
    // uma div própria aqui dentro. O fundo do tema fica `fixed` atrás para
    // não esticar/repetir ao longo de uma carta grande.
    <section
      aria-label={`Carta para ${recipient}`}
      className="relative min-h-screen w-full overflow-x-hidden"
    >
      <div aria-hidden="true" className="mv-bg-soft pointer-events-none fixed inset-0" />

      <div className="relative flex min-h-screen items-center justify-center px-5 py-12 sm:px-8">
        <article
          className={`
            mv-glass w-full max-w-2xl px-7 py-10 sm:px-12 sm:py-14
            transition-[opacity,transform] duration-1400 ease-out
            ${isVisible ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"}
          `}
        >
          <header className="text-center">
            <p className="mv-label leading-loose">
              Uma mensagem especial para
            </p>

            <h1 className="mv-serif mt-3 wrap-break-word text-[clamp(3.25rem,15vw,5.5rem)] italic leading-[1.05] text-(--mv-accent-soft)">
              {recipient}
            </h1>

            {formattedEventDate && (
              <time
                dateTime={eventDate}
                className="mt-4 block text-sm text-(--mv-accent-soft) opacity-90"
              >
                {formattedEventDate}
              </time>
            )}

            <div aria-hidden="true" className="mv-divider mx-auto mt-6 w-48">
              <ThemeGlyph kind={tokens.divider} className="h-5 w-5" />
            </div>
          </header>

          {/* Segunda pergunta contextual do wizard (contextAnswer). Rótulo é a
              própria pergunta (contextQuestion, resolvida em ExperienceViewer
              a partir de informationStepConfig.ts) — o fallback abaixo só
              existe para um contextQuestion ausente. Só existe quando o
              usuário de fato respondeu. wrap-anywhere (não wrap-break-word): uma
              sequência contínua sem espaços precisa poder quebrar mesmo
              dentro do card. */}
          {contextAnswer && (
            <div className="mt-10">
              <p className="flex items-start gap-3">
                <ThemeGlyph kind="heart" className="mt-0.5 h-5 w-5 shrink-0" />
                <span className="mv-label font-semibold leading-relaxed text-(--mv-accent)">
                  {contextQuestion ?? "Uma coisa que torna isso ainda mais especial"}
                </span>
              </p>

              <p className="mv-serif mt-4 whitespace-pre-wrap wrap-anywhere text-[1.25rem] leading-[1.8] text-(--mv-text) sm:text-[1.35rem]">
                {contextAnswer}
              </p>
            </div>
          )}

          {/* Sem scroll interno (pedido explícito): o texto flui na altura
              real que precisar, e é a página que rola. */}
          <p
            className={`mv-serif whitespace-pre-wrap wrap-anywhere text-[1.25rem] leading-[1.8] text-(--mv-text) sm:text-[1.35rem] ${contextAnswer ? "mt-8" : "mt-10"}`}
          >
            {body}
          </p>

          {closing && (
            <p className="mv-serif mt-4 flex items-center gap-2 wrap-break-word text-[2.5rem] italic leading-tight text-(--mv-accent)">
              {closing}
              <ThemeGlyph kind={tokens.divider} className="h-6 w-6 shrink-0" />
            </p>
          )}

          {creator && (
            <footer className="mt-10 border-t border-white/15 pt-6 text-right">
              <p className="mv-label">
                Com carinho,
              </p>
              <p className="mv-serif mt-2 text-2xl italic text-(--mv-text)">
                {creator}
              </p>
            </footer>
          )}

          <div className="mt-10 flex justify-center">
            <button
              type="button"
              onClick={onComplete}
              disabled={!showContinue}
              aria-hidden={!showContinue}
              className={`
                mv-pill transition-[opacity,transform] duration-500
                ${showContinue ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-2 opacity-0"}
              `}
            >
              Continuar <span aria-hidden="true">→</span>
            </button>
          </div>
        </article>
      </div>
    </section>
  );
}
