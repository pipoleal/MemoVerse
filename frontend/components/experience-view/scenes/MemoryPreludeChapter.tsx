"use client";

import { useEffect, useState } from "react";

import { DEFAULT_THEME_CODE, THEME_REGISTRY, type ThemeVisual } from "@/lib/themeRegistry";

type MemoryPreludeChapterProps = {
  theme?: ThemeVisual;
  message?: string;
};

const defaultPreludeMessage =
  "Uma mensagem especial aparecerá aqui.";

const particles = [
  ["12%", "-20%", "0.2s"],
  ["-18%", "-9%", "0.55s"],
  ["26%", "8%", "0.9s"],
  ["-30%", "18%", "1.2s"],
  ["5%", "30%", "1.55s"],
  ["-8%", "-32%", "1.8s"],
] as const;

export default function MemoryPreludeChapter({
  theme = THEME_REGISTRY[DEFAULT_THEME_CODE],
  message,
}: MemoryPreludeChapterProps) {
  const [showMessage, setShowMessage] = useState(false);
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    const messageTimer = window.setTimeout(() => setShowMessage(true), 4600);
    const hintTimer = window.setTimeout(() => setShowHint(true), 5400);

    return () => {
      window.clearTimeout(messageTimer);
      window.clearTimeout(hintTimer);
    };
  }, []);

  return (
    <section
      aria-label="O nascimento de uma nova estrela"
      className={`memory-prelude relative isolate flex min-h-screen w-full items-center justify-center overflow-hidden text-white ${theme.gradient}`}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(29,45,85,0.22)_0%,rgba(2,4,10,0)_44%,#02040a_82%)]" />

      <div className="star-system pointer-events-none absolute left-1/2 top-1/2 h-0 w-0">
        <div className="star-illumination absolute left-1/2 top-1/2 h-[75vmax] w-[75vmax] -translate-x-1/2 -translate-y-1/2 rounded-full" />
        <div className="star-halo absolute left-1/2 top-1/2 h-32 w-32 -translate-x-1/2 -translate-y-1/2 rounded-full" />
        <div className="star-core absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full" />

        {particles.map(([x, y, delay], index) => (
          <span
            key={`${x}-${y}`}
            className="star-particle absolute left-1/2 top-1/2 h-1 w-1 rounded-full bg-[#dce9ff]"
            style={{
              "--particle-x": x,
              "--particle-y": y,
              animationDelay: delay,
              opacity: index % 2 === 0 ? 0.75 : 0.5,
            } as React.CSSProperties}
          />
        ))}
      </div>

      <div className="absolute inset-0 z-20 flex h-full flex-col items-center justify-end px-6 pb-16 text-center sm:pb-20">
        {showMessage && (
          <div className="max-w-md animate-[message-arrive_1400ms_ease-out_both]">
            <p className="text-lg font-light leading-relaxed tracking-wide text-white/80 sm:text-xl">
              {message || defaultPreludeMessage}
            </p>
          </div>
        )}

        {showHint && (
          <p className="mt-10 animate-[message-arrive_700ms_ease-out_both] text-xs uppercase tracking-[0.4em] text-white/40">
            <span className="inline-block animate-bounce motion-reduce:animate-none" aria-hidden="true">
              ↓
            </span>
            <span className="ml-3">role para ver as memórias</span>
          </p>
        )}
      </div>

      <style jsx>{`
        .star-system { animation: awaken 4.6s cubic-bezier(0.16, 1, 0.3, 1) both; }
        .star-core {
          background: #fffdf2;
          box-shadow: 0 0 8px 2px rgba(255, 250, 220, 0.95), 0 0 32px 10px rgba(189, 211, 255, 0.52), 0 0 90px 28px rgba(105, 142, 255, 0.18);
          animation: core-born 4.6s cubic-bezier(0.16, 1, 0.3, 1) both, core-pulse 3.6s 4.6s ease-in-out infinite;
        }
        .star-halo {
          border: 1px solid rgba(209, 225, 255, 0.26);
          box-shadow: inset 0 0 32px rgba(177, 204, 255, 0.1), 0 0 56px rgba(133, 169, 255, 0.18);
          animation: halo-born 4.6s cubic-bezier(0.16, 1, 0.3, 1) both;
        }
        .star-illumination {
          background: radial-gradient(circle, rgba(189, 213, 255, 0.14) 0%, rgba(128, 162, 255, 0.05) 21%, transparent 55%);
          animation: illuminate 4.6s ease-out both;
        }
        .star-particle {
          box-shadow: 0 0 8px 2px rgba(205, 222, 255, 0.8);
          animation: particle-appear 2.1s ease-out both;
        }
        @keyframes awaken { from { opacity: 0; } 18% { opacity: 1; } to { opacity: 1; } }
        @keyframes core-born { 0%, 16% { transform: translate(-50%, -50%) scale(0.2); opacity: 0; } 31% { transform: translate(-50%, -50%) scale(0.8); opacity: 1; } 52% { transform: translate(-50%, -50%) scale(0.55); } 78%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; } }
        @keyframes core-pulse { 0%, 100% { filter: brightness(1); } 50% { filter: brightness(1.3); } }
        @keyframes halo-born { 0%, 30% { transform: translate(-50%, -50%) scale(0.12); opacity: 0; } 66% { opacity: 0.55; } 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.35; } }
        @keyframes illuminate { 0%, 28% { opacity: 0; } 100% { opacity: 1; } }
        @keyframes particle-appear { 0%, 20% { transform: translate(-50%, -50%) scale(0); opacity: 0; } 100% { transform: translate(var(--particle-x), var(--particle-y)) scale(1); opacity: inherit; } }
        @keyframes message-arrive { from { transform: translateY(0.75rem); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
        @media (prefers-reduced-motion: reduce) {
          .star-system, .star-core, .star-halo, .star-illumination, .star-particle { animation-duration: 0.01ms; animation-iteration-count: 1; }
        }
      `}</style>
    </section>
  );
}
