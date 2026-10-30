"use client";

import type { CSSProperties } from "react";

type MemoryPreludeChapterProps = {
  message?: string;
  recipient: string;
  // Mesmo eventDate do wizard ("AAAA-MM-DD") — só o ano é usado, grande ao
  // fundo. Vazio/ inválido simplesmente não mostra ano nenhum.
  eventDate?: string;
  // Sem nenhuma foto/vídeo não há o que rolar (MemoriesCanvas avança
  // sozinho), então a dica "Role para ver as memórias" não aparece.
  hasMedia: boolean;
};

const defaultPreludeMessage =
  "Uma mensagem especial aparecerá aqui.";

function delay(ms: number) {
  return { "--mv-delay": `${ms}ms` } as CSSProperties;
}

// Tela "Cena": duas estrelas (você e o destinatário) orbitando, o ano em
// que a história começou ao fundo e a mensagem curta do wizard
// (shortMessage) centralizada. Tudo em CSS (transform/opacity) — a órbita
// gira o "braço" inteiro e cada rótulo gira ao contrário para continuar
// na horizontal.
export default function MemoryPreludeChapter({
  message,
  recipient,
  eventDate,
  hasMedia,
}: MemoryPreludeChapterProps) {
  const year = /^\d{4}/.exec(eventDate ?? "")?.[0];

  return (
    <section
      aria-label="O começo da nossa história"
      className="mv-bg-dark relative isolate flex flex-1 flex-col items-center overflow-hidden px-6 pb-8 pt-[10vh] text-center"
    >
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-[38%] -z-10 h-[130vw] max-h-[60rem] w-[130vw] max-w-[60rem] -translate-x-1/2 -translate-y-1/2 rounded-full"
        style={{
          background:
            "radial-gradient(circle, color-mix(in srgb, var(--mv-strong) 55%, transparent) 0%, color-mix(in srgb, var(--mv-secondary) 30%, transparent) 40%, transparent 70%)",
        }}
      />

      <div aria-hidden="true" className="mv-rise relative aspect-square w-[min(82vw,22rem)]">
        {year && (
          <span className="mv-serif pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 select-none text-[clamp(8rem,42vw,15rem)] leading-none text-white/[0.07]">
            {year}
          </span>
        )}

        <div className="absolute inset-0 rounded-full border border-white/10" />

        <div className="mv-pulse absolute left-1/2 top-1/2 h-16 w-16 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--mv-accent)_45%,transparent)_0%,transparent_70%)]" />

        {/* Braço da órbita: anel interno + rastros + as duas estrelas. */}
        <div className="mv-orbit absolute inset-[11%]">
          <svg viewBox="-100 -100 200 200" className="absolute inset-0 h-full w-full overflow-visible">
            <circle r="99" fill="none" stroke="#fff" strokeOpacity="0.28" />
            <path
              d="M 0 -99 A 99 99 0 0 0 -85.7 -49.5"
              fill="none"
              stroke="var(--mv-accent-soft)"
              strokeOpacity="0.7"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeDasharray="0.1 6"
            />
            <path
              d="M 0 99 A 99 99 0 0 0 85.7 49.5"
              fill="none"
              stroke="#fff"
              strokeOpacity="0.6"
              strokeWidth="2.4"
              strokeLinecap="round"
              strokeDasharray="0.1 6"
            />
          </svg>

          <OrbitStar position="top" label={recipient} color="#dfe3ff" />
          <OrbitStar position="bottom" label="você" color="#ffffff" />
        </div>
      </div>

      <p
        className="mv-serif mv-rise mt-10 max-w-md whitespace-pre-wrap wrap-anywhere text-[1.45rem] leading-[1.6] text-(--mv-text) sm:text-[1.65rem]"
        style={delay(500)}
      >
        {message || defaultPreludeMessage}
      </p>

      {hasMedia && (
        <p className="mv-rise mt-auto flex flex-col items-center gap-3 pt-10" style={delay(1300)}>
          <span className="mv-label">Role para ver as memórias</span>
          <svg viewBox="0 0 24 24" aria-hidden="true" className="mv-nudge h-5 w-5 text-(--mv-accent)">
            <path d="m6 6 6 6 6-6M6 12l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </p>
      )}
    </section>
  );
}

function OrbitStar({ position, label, color }: { position: "top" | "bottom"; label: string; color: string }) {
  return (
    <div
      className={`absolute left-1/2 h-4 w-4 -translate-x-1/2 ${position === "top" ? "-top-2" : "-bottom-2"}`}
    >
      {/* Gira ao contrário do braço: o rótulo continua sempre na horizontal. */}
      <div className="mv-orbit-reverse relative h-full w-full">
        <span
          className="mv-pulse absolute -inset-4 rounded-full"
          style={{ background: `radial-gradient(circle, ${color}66 0%, transparent 70%)` }}
        />
        <span className="absolute inset-0 rounded-full" style={{ background: color, boxShadow: `0 0 12px ${color}` }} />
        <span className="mv-serif absolute left-[calc(100%+0.5rem)] top-1/2 -translate-y-1/2 whitespace-nowrap text-lg italic text-(--mv-accent-soft)">
          {label}
        </span>
      </div>
    </div>
  );
}
