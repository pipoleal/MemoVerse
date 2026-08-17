"use client";

import { useEffect, useState } from "react";

type RecipientRevealChapterProps = {
  recipient: string;
  title?: string;
  onComplete: () => void;
};

type RevealPhase =
  | "star"
  | "reveal"
  | "recipient"
  | "exit";

export default function RecipientRevealChapter({
  recipient,
  title,
  onComplete,
}: RecipientRevealChapterProps) {
  const [phase, setPhase] =
    useState<RevealPhase>("star");

  useEffect(() => {
    const revealTimer = setTimeout(() => {
      setPhase("reveal");
    }, 900);

    const recipientTimer = setTimeout(() => {
      setPhase("recipient");
    }, 2200);

    const exitTimer = setTimeout(() => {
      setPhase("exit");
    }, 5900);

    const completeTimer = setTimeout(() => {
      onComplete();
    }, 7300);

    return () => {
      clearTimeout(revealTimer);
      clearTimeout(recipientTimer);
      clearTimeout(exitTimer);
      clearTimeout(completeTimer);
    };
  }, [onComplete]);

  const showStar =
    phase === "star" ||
    phase === "reveal";

  const showRecipient =
    phase === "recipient";

  const isExiting = phase === "exit";

  return (
    <section className="absolute inset-0 overflow-hidden bg-black text-white">
      <div
        className={`
          pointer-events-none absolute left-1/2 top-1/2 rounded-full bg-white
          transition-all ease-out
          ${
            showStar
              ? "h-2 w-2 -translate-x-1/2 -translate-y-1/2 opacity-100 duration-[900ms]"
              : "h-4 w-4 -translate-x-1/2 -translate-y-1/2 scale-[5] opacity-0 duration-[1800ms]"
          }
        `}
        style={{
          boxShadow:
            "0 0 12px 4px rgba(255,255,255,0.9), 0 0 45px 18px rgba(255,255,255,0.45), 0 0 120px 50px rgba(120,160,255,0.18)",
        }}
      />

      <div
        className={`
          pointer-events-none absolute left-1/2 top-1/2 rounded-full border border-white/10
          transition-all ease-out
          ${
            phase === "reveal"
              ? "h-[42vh] w-[42vh] -translate-x-1/2 -translate-y-1/2 scale-100 opacity-100 duration-[1800ms]"
              : "h-16 w-16 -translate-x-1/2 -translate-y-1/2 scale-50 opacity-0 duration-[900ms]"
          }
        `}
        style={{
          boxShadow:
            "0 0 100px 20px rgba(120,160,255,0.08)",
        }}
      />

      <div className="relative flex min-h-full items-center justify-center px-6 text-center">
        <div
          className={`
            w-full max-w-5xl transition-all ease-out
            ${
              showRecipient
                ? "translate-y-0 opacity-100 duration-[1500ms]"
                : "translate-y-8 opacity-0 duration-[1000ms]"
            }
            ${
              isExiting
                ? "-translate-y-6 opacity-0 duration-[1400ms]"
                : ""
            }
          `}
        >
          <p className="text-xs uppercase tracking-[0.5em] text-white/45 sm:text-sm">
            Uma história feita para
          </p>

          <h1 className="mt-5 text-5xl font-light tracking-wide text-white drop-shadow-[0_0_30px_rgba(255,255,255,0.15)] sm:text-6xl md:text-7xl lg:text-8xl">
            {recipient}
          </h1>

          {title && (
            <p className="mx-auto mt-6 max-w-2xl text-xs uppercase tracking-[0.35em] text-white/40 sm:text-sm">
              {title}
            </p>
          )}
        </div>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_20%,rgba(0,0,0,0.72)_100%)]" />
    </section>
  );
}
