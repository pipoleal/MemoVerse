"use client";

import { useEffect, useRef, useState } from "react";

import type { GlyphKind, OrnamentKind } from "@/lib/themeRegistry";

import ThemeGlyph from "../theme/ThemeGlyph";
import ThemeOrnament from "../theme/ThemeOrnament";

type RecipientRevealChapterProps = {
  recipient: string;
  title?: string;
  ornament?: OrnamentKind;
  divider?: GlyphKind;
  onComplete: () => void;
};

type RevealPhase =
  | "star"
  | "reveal"
  | "recipient"
  | "exit";

// Constelação discreta da parte de baixo (coordenadas em % da tela).
const CONSTELLATION = [
  [15, 72],
  [28, 78],
  [41, 74],
  [64, 82],
  [80, 77],
] as const;

// Tempo da saída (fade com subida) antes de avançar para a Mensagem.
const EXIT_DURATION = 1000;

export default function RecipientRevealChapter({
  recipient,
  title,
  ornament = "none",
  divider = "sparkle",
  onComplete,
}: RecipientRevealChapterProps) {
  const [phase, setPhase] =
    useState<RevealPhase>("star");
  const [canContinue, setCanContinue] = useState(false);

  // ExperienceViewer passa uma arrow function nova a cada render — guardada
  // num ref para que os timers abaixo nunca reiniciem por causa disso.
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    const revealTimer = setTimeout(() => {
      setPhase("reveal");
    }, 900);

    const recipientTimer = setTimeout(() => {
      setPhase("recipient");
    }, 2200);

    // Antes avançava sozinho após ~7s; agora, como no layout, espera o
    // "Toque para continuar".
    const hintTimer = setTimeout(() => {
      setCanContinue(true);
    }, 3600);

    return () => {
      clearTimeout(revealTimer);
      clearTimeout(recipientTimer);
      clearTimeout(hintTimer);
    };
  }, []);

  useEffect(() => {
    if (phase !== "exit") return;
    const completeTimer = setTimeout(() => onCompleteRef.current(), EXIT_DURATION);
    return () => clearTimeout(completeTimer);
  }, [phase]);

  function handleContinue() {
    if (!canContinue || phase === "exit") return;
    setPhase("exit");
  }

  const showStar =
    phase === "star" ||
    phase === "reveal";

  const showRecipient =
    phase === "recipient";

  const isExiting = phase === "exit";

  return (
    <section
      onClick={handleContinue}
      className={`mv-bg-dark absolute inset-0 overflow-hidden ${canContinue && !isExiting ? "cursor-pointer" : ""}`}
    >
      <div
        className={`transition-opacity duration-1800 ${showStar ? "opacity-0" : "opacity-100"}`}
      >
        <ThemeOrnament kind={ornament} />

        <svg aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full" preserveAspectRatio="none">
          <polyline
            points={CONSTELLATION.map(([x, y]) => `${x}%,${y}%`).join(" ")}
            fill="none"
            stroke="var(--mv-accent-soft)"
            strokeOpacity="0.18"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {CONSTELLATION.map(([x, y], index) => (
          <span
            key={`${x}-${y}`}
            aria-hidden="true"
            className="mv-pulse pointer-events-none absolute h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-(--mv-accent-soft) opacity-70"
            style={{ left: `${x}%`, top: `${y}%`, animationDelay: `${index * 0.5}s` }}
          />
        ))}
      </div>

      {/* Ponto de luz inicial que "abre" a cena — mantido da versão
          anterior, agora na cor do tema. */}
      <div
        className={`
          pointer-events-none absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white
          transition-[opacity,transform] ease-out
          ${showStar ? "scale-100 opacity-100 duration-900" : "scale-[6] opacity-0 duration-1800"}
        `}
        style={{
          boxShadow:
            "0 0 12px 4px rgba(255,255,255,0.9), 0 0 45px 18px color-mix(in srgb, var(--mv-accent) 45%, transparent)",
        }}
      />

      <div className="relative flex min-h-full items-center justify-center px-6 text-center">
        <div
          className={`
            w-full max-w-5xl transition-[opacity,transform] ease-out
            ${
              showRecipient
                ? "translate-y-0 opacity-100 duration-1500"
                : isExiting
                  ? "-translate-y-6 opacity-0 duration-1000"
                  : "translate-y-8 opacity-0 duration-1000"
            }
          `}
        >
          <p className="mv-label">
            Uma história feita para
          </p>

          <h1 className="mv-serif mt-4 wrap-break-word text-[clamp(4rem,19vw,9rem)] font-medium italic leading-[1.05] text-(--mv-text) drop-shadow-[0_0_30px_rgba(255,255,255,0.12)]">
            {recipient}
          </h1>

          <div aria-hidden="true" className="mv-divider mx-auto mt-6 w-56">
            <ThemeGlyph kind={divider} className="h-5 w-5" />
          </div>

          {title && (
            <p className="mv-label mx-auto mt-6 max-w-sm leading-loose">
              {title}
            </p>
          )}
        </div>
      </div>

      <div
        className={`absolute inset-x-0 bottom-[6vh] flex justify-center transition-opacity duration-700 ${
          canContinue && !isExiting ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      >
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            handleContinue();
          }}
          tabIndex={canContinue ? 0 : -1}
          className="mv-focus flex flex-col items-center gap-4 rounded-2xl px-4 py-2"
        >
          <span aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-full border border-(--mv-accent-soft)/40">
            <span className="mv-pulse h-2.5 w-2.5 rounded-full bg-(--mv-accent)" />
          </span>
          <span className="mv-label">Toque para continuar</span>
        </button>
      </div>
    </section>
  );
}
