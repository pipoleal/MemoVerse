"use client";

import {
  useEffect,
  useRef,
  useState,
} from "react";

import StarField from "../StarField";
import EarthCanvas from "./EarthCanvas";

type StarFieldPhase =
  | "idle"
  | "transition"
  | "burst"
  | "converge";

type PlanetSceneProps = {
  onStart: () => void;
  onStarsComplete?: () => void;
  started?: boolean;
};

export default function PlanetScene({
  onStart,
  onStarsComplete,
  started = false,
}: PlanetSceneProps) {
  const [showPhrase, setShowPhrase] =
    useState(false);

  const [phraseStep, setPhraseStep] =
    useState(0);

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

  useEffect(() => {
    const phraseTimer = setTimeout(() => {
      setShowPhrase(true);
    }, 6500);

    const word1 = setTimeout(() => {
      setPhraseStep(1);
    }, 6800);

    const word2 = setTimeout(() => {
      setPhraseStep(2);
    }, 7400);

    const word3 = setTimeout(() => {
      setPhraseStep(3);
    }, 8000);

    const word4 = setTimeout(() => {
      setPhraseStep(4);
    }, 8600);

    const buttonTimer = setTimeout(() => {
      setShowButton(true);
    }, 9800);

    return () => {
      clearTimeout(phraseTimer);
      clearTimeout(word1);
      clearTimeout(word2);
      clearTimeout(word3);
      clearTimeout(word4);
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
    console.log(
      "MEMOVERSE: botão clicado"
    );

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

    /*
     * ========================================
     * FINAL
     *
     * A convergência dura 2.2 segundos.
     *
     * Depois disso:
     *
     * ✦ → ClientIntroScene
     * ========================================
     */

    completeTimerRef.current =
      setTimeout(() => {
        onStarsComplete?.();
      }, 7200);
  }

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-black">

      {/* =========================================
          ESTRELAS
          ========================================= */}

      <div className="pointer-events-none absolute inset-0 z-0">
        <StarField phase={starPhase} />
      </div>

      {/* =========================================
          TERRA
          ========================================= */}

      <div
        className={`
          pointer-events-none
          absolute
          inset-0
          z-10
          transition-all
          duration-2200ms
          ease-in-out
          ${
            starPhase === "idle"
              ? "scale-100 opacity-100"
              : starPhase === "transition"
                ? "scale-100 opacity-100"
                : "scale-[0.92] opacity-0"
          }
        `}
      >
        <EarthCanvas />
      </div>

      {/* =========================================
          VINHETA
          ========================================= */}

      <div
        className="
          pointer-events-none
          absolute
          inset-0
          z-20
          bg-[radial-gradient(circle_at_center,transparent_30%,rgba(0,0,0,0.7)_100%)]
        "
      />

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
          pb-[10vh]
          transition-all
          duration-1200ms
          ease-out
          ${
            started
              ? "pointer-events-none translate-y-6 opacity-0"
              : "translate-y-0 opacity-100"
          }
        `}
      >
        <div className="flex flex-col items-center px-6 text-center">

          {/* FRASE */}

          <div
            className={`
              max-w-3xl
              transition-all
              duration-1500ms
              ease-out
              ${
                showPhrase
                  ? "translate-y-0 opacity-100"
                  : "translate-y-8 opacity-0"
              }
            `}
          >
            <p
              className="
                text-2xl
                font-light
                leading-relaxed
                tracking-wide
                text-white
                md:text-4xl
              "
            >
              <span
                className={`
                  inline-block
                  transition-all
                  duration-700
                  ${
                    phraseStep >= 1
                      ? "translate-y-0 opacity-100"
                      : "translate-y-3 opacity-0"
                  }
                `}
              >
                Toda
              </span>{" "}

              <span
                className={`
                  inline-block
                  transition-all
                  duration-700
                  ${
                    phraseStep >= 2
                      ? "translate-y-0 opacity-100"
                      : "translate-y-3 opacity-0"
                  }
                `}
              >
                memória
              </span>{" "}

              <span
                className={`
                  inline-block
                  transition-all
                  duration-700
                  ${
                    phraseStep >= 3
                      ? "translate-y-0 opacity-100"
                      : "translate-y-3 opacity-0"
                  }
                `}
              >
                se transforma em uma
              </span>{" "}

              <span
                className={`
                  inline-block
                  font-medium
                  text-yellow-200
                  transition-all
                  duration-1000
                  ${
                    phraseStep >= 4
                      ? "scale-100 translate-y-0 opacity-100"
                      : "scale-90 translate-y-3 opacity-0"
                  }
                `}
              >
                estrela. ⭐
              </span>
            </p>
          </div>

          {/* BOTÃO */}

          <div
            className={`
              pointer-events-auto
              transition-all
              duration-1400ms
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
              className="
                mt-8
                cursor-pointer
                rounded-full
                border
                border-white/20
                bg-white/10
                px-8
                py-4
                text-sm
                font-semibold
                uppercase
                tracking-[0.25em]
                text-white
                backdrop-blur-md
                transition-all
                duration-500
                hover:scale-105
                hover:border-yellow-300/60
                hover:bg-yellow-300/10
                hover:text-yellow-200
              "
            >
              Começar experiência ✨
            </button>
          </div>

        </div>
      </div>

    </section>
  );
}