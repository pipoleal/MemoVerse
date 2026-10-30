"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import StarField from "../StarField";
import ThemeGlyph from "../theme/ThemeGlyph";
import ThemePlanet from "../theme/ThemePlanet";

type StarFieldPhase =
  | "idle"
  | "transition"
  | "burst"
  | "converge";

type PlanetSceneProps = {
  onStart: () => void;
  onStarsComplete?: () => void;
  started?: boolean;
  // Só mostra "Ative o som..." quando há de fato uma música configurada.
  hasMusic?: boolean;
};

export default function PlanetScene({
  onStart,
  onStarsComplete,
  started = false,
  hasMusic = false,
}: PlanetSceneProps) {
  const [showPhrase, setShowPhrase] =
    useState(false);

  const [showButton, setShowButton] =
    useState(false);

  const [starPhase, setStarPhase] =
    useState<StarFieldPhase>("idle");

  const burstTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null
    );

  const convergeTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null
    );

  const completeTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null
    );

  /*
   * ==========================================
   * ANIMAÇÃO INICIAL
   * ==========================================
   */

  // Antes a frase esperava ~6,5s pela entrada da Terra em WebGL; o planeta
  // agora é SVG (ThemePlanet) e já está na tela, e a Prévia vem antes —
  // então a frase e o botão entram logo, só com o fade com subida.
  useEffect(() => {
    const phraseTimer = setTimeout(() => {
      setShowPhrase(true);
    }, 700);

    const buttonTimer = setTimeout(() => {
      setShowButton(true);
    }, 1900);

    return () => {
      clearTimeout(phraseTimer);
      clearTimeout(buttonTimer);
    };
  }, []);

  /*
   * ==========================================
   * LIMPEZA
   * ==========================================
   */

  useEffect(() => {
    return () => {
      if (burstTimerRef.current) {
        clearTimeout(burstTimerRef.current);
      }

      if (convergeTimerRef.current) {
        clearTimeout(
          convergeTimerRef.current
        );
      }

      if (completeTimerRef.current) {
        clearTimeout(
          completeTimerRef.current
        );
      }
    };
  }, []);

  /*
   * ==========================================
   * COMEÇAR EXPERIÊNCIA
   * ==========================================
   */

  function handleStart() {
    /*
     * FASE 1
     *
     * Estrelas começam a orbitar.
     */
    setStarPhase("transition");

    /*
     * O componente pai sabe que
     * a experiência começou.
     */
    onStart();

    /*
     * ========================================
     * FASE 2
     *
     * Explosão / aceleração.
     * ========================================
     */

    burstTimerRef.current =
      setTimeout(() => {
        setStarPhase("burst");
      }, 2200);

    /*
     * ========================================
     * FASE 3
     *
     * As estrelas começam a convergir
     * para o centro.
     *
     * O burst dura aproximadamente
     * 2.5 segundos.
     * ========================================
     */

    convergeTimerRef.current =
      setTimeout(() => {
        setStarPhase("converge");
      }, 4700);

    // A convergência dura 2.2 segundos; ao final, onStarsComplete avança
    // para o próximo capítulo (RecipientRevealChapter).
    completeTimerRef.current =
      setTimeout(() => {
        onStarsComplete?.();
      }, 7200);
  }

  return (
    <section className="mv-bg-dark relative min-h-screen w-full overflow-hidden">

      {/* =========================================
          ESTRELAS
          ========================================= */}

      <div className="pointer-events-none absolute inset-0 z-0">
        <StarField phase={starPhase} />
      </div>

      {/* =========================================
          PLANETA DO TEMA
          ========================================= */}

      <div
        className={`
          pointer-events-none
          absolute
          inset-x-0
          top-[4vh]
          bottom-[44%]
          z-10
          flex
          items-center
          justify-center
          transition-[opacity,transform]
          duration-2200
          ease-in-out
          ${
            starPhase === "idle" || starPhase === "transition"
              ? "scale-100 opacity-100"
              : "scale-[0.92] opacity-0"
          }
        `}
      >
        {/* Altura limitada à metade de cima da tela: em telas baixas o
            planeta encolhe em vez de ficar atrás da frase. */}
        <div className="aspect-[520/460] h-full max-h-[27rem] max-w-full">
          <ThemePlanet />
        </div>
      </div>

      {/* =========================================
          CONTEÚDO INICIAL
          ========================================= */}

      <div
        className={`
          absolute
          inset-0
          z-30
          flex
          items-end
          justify-center
          pb-[8vh]
          transition-[opacity,transform]
          duration-1200
          ease-out
          ${
            started
              ? "pointer-events-none translate-y-6 opacity-0"
              : "translate-y-0 opacity-100"
          }
        `}
      >
        <div className="flex w-full max-w-lg flex-col items-center px-6 text-center">
          {showPhrase && (
            <p className="mv-serif mv-rise text-[min(2.35rem,5.4vh)] leading-[1.15] text-(--mv-text) sm:text-[min(2.85rem,5.4vh)]">
              Toda memória
              <br />
              se transforma em uma
              <br />
              <span className="inline-flex items-center gap-3 italic text-(--mv-gold)">
                estrela.
                <ThemeGlyph kind="sparkle" className="mv-pulse h-7 w-7" />
              </span>
            </p>
          )}

          <div
            className={`
              mt-[min(2.5rem,4vh)]
              flex
              w-full
              flex-col
              items-center
              transition-[opacity,transform]
              duration-1000
              ease-out
              ${
                showButton
                  ? "translate-y-0 opacity-100"
                  : "pointer-events-none translate-y-6 opacity-0"
              }
            `}
          >
            <button
              type="button"
              onClick={handleStart}
              disabled={!showButton || started}
              className="mv-pill w-full max-w-sm bg-white/10 py-5"
            >
              Começar experiência
              <ThemeGlyph kind="sparkle" className="h-4 w-4" />
            </button>

            {hasMusic && (
              <p className="mt-5 flex items-center gap-2 text-sm text-(--mv-accent-soft) opacity-80">
                <svg viewBox="0 0 24 24" aria-hidden="true" className="h-4 w-4 fill-current">
                  <path d="M10 3v11.3A3.5 3.5 0 1 0 12 17.5V8h6V3h-8Z" />
                </svg>
                Ative o som para a experiência completa
              </p>
            )}
          </div>
        </div>
      </div>

    </section>
  );
}
