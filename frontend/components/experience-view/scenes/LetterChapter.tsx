"use client";

import { useEffect, useMemo, useState } from "react";

import { getThemeVisual } from "@/lib/themeRegistry";

type LetterChapterProps = {
  recipient: string;
  creator: string;
  letter: string;
  theme: string;
  eventDate: string;
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

export default function LetterChapter({
  recipient,
  creator,
  letter,
  theme,
  eventDate,
  onComplete,
}: LetterChapterProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [showContinue, setShowContinue] = useState(false);

  const letterTheme = useMemo(
    () => getThemeVisual(theme).letter,
    [theme]
  );

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
    <section
      aria-label={`Carta para ${recipient}`}
      className={`absolute inset-0 overflow-hidden text-white ${letterTheme.backdropClass}`}
    >
      <div
        className={`pointer-events-none absolute left-1/2 top-0 h-72 w-72 -translate-x-1/2 -translate-y-1/2 rounded-full blur-3xl ${letterTheme.glowClass}`}
      />

      <div
        className={`pointer-events-none absolute left-[12%] top-[22%] h-px w-24 ${letterTheme.ornamentClass}`}
      />

      <div
        className={`pointer-events-none absolute bottom-[18%] right-[10%] h-24 w-24 rounded-full border ${letterTheme.ornamentClass}`}
      />

      <div className="relative flex min-h-full items-center justify-center px-5 py-10 sm:px-8">
        <article
          className={`
            w-full max-w-3xl rounded-[2rem] border p-7 shadow-[0_30px_100px_rgba(0,0,0,0.45)] backdrop-blur-xl
            transition-all duration-[1400ms] ease-out sm:p-10 md:p-14
            ${letterTheme.cardClass}
            ${
              isVisible
                ? "translate-y-0 scale-100 opacity-100"
                : `${letterTheme.entryClass} opacity-0`
            }
          `}
        >
          <header className="text-center">
            <p
              className={`text-xs font-medium uppercase tracking-[0.35em] sm:tracking-[0.45em] ${letterTheme.secondaryClass}`}
            >
              Uma mensagem especial para
            </p>

            <h1
              className={`mt-4 break-words text-4xl font-light tracking-wide sm:text-5xl md:text-6xl ${letterTheme.primaryClass}`}
            >
              {recipient}
            </h1>

            {formattedEventDate && (
              <time
                dateTime={eventDate}
                className={`mt-4 block text-sm ${letterTheme.secondaryClass}`}
              >
                {formattedEventDate}
              </time>
            )}
          </header>

          <div
            aria-hidden="true"
            className={`mx-auto my-8 h-px w-16 ${letterTheme.ornamentClass}`}
          />

          <div className="max-h-[min(48vh,28rem)] overflow-y-auto pr-2">
            <p
              className={`whitespace-pre-wrap break-words text-base leading-8 sm:text-lg sm:leading-9 ${letterTheme.textClass}`}
            >
              {letter}
            </p>
          </div>

          {creator && (
            <footer className="mt-8 border-t border-white/10 pt-6 text-right">
              <p className={`text-sm ${letterTheme.secondaryClass}`}>
                Com carinho,
              </p>
              <p className={`mt-1 text-lg ${letterTheme.primaryClass}`}>
                {creator}
              </p>
            </footer>
          )}

          <div className="mt-8 flex justify-center">
            <button
              type="button"
              onClick={onComplete}
              disabled={!showContinue}
              aria-hidden={!showContinue}
              className={`
                min-h-11 rounded-full border px-5 py-2 text-sm font-medium tracking-wide
                transition-all duration-500 focus-visible:outline-2 focus-visible:outline-offset-4
                ${letterTheme.ornamentClass}
                ${letterTheme.primaryClass}
                ${
                  showContinue
                    ? "translate-y-0 opacity-100 hover:bg-white/10"
                    : "pointer-events-none translate-y-2 opacity-0"
                }
              `}
            >
              Continuar <span aria-hidden="true">→</span>
            </button>
          </div>
        </article>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_30%,rgba(0,0,0,0.65)_100%)]" />
    </section>
  );
}
