"use client";

import { useMemo } from "react";

import type { GlyphKind } from "@/lib/themeRegistry";

import ThemeGlyph from "../theme/ThemeGlyph";

type PreviewChapterProps = {
  recipient: string;
  letter: string;
  seal: GlyphKind;
  divider: GlyphKind;
  onContinue: () => void;
};

// Só um trecho — o resto se desfaz (mv-fade-out) e a carta inteira aparece
// depois, na tela Mensagem (LetterChapter).
const EXCERPT_LENGTH = 420;

// Primeira linha curta terminada em vírgula ("Marina,") vira a saudação em
// itálico, como no layout; qualquer outra carta começa direto no corpo.
function splitSalutation(letter: string) {
  const trimmed = letter.trim();
  const [firstLine, ...rest] = trimmed.split("\n");

  if (rest.length > 0 && firstLine.trim().length <= 40 && firstLine.trim().endsWith(",")) {
    return { salutation: firstLine.trim(), body: rest.join("\n").trim() };
  }

  return { salutation: null, body: trimmed };
}

export default function PreviewChapter({ recipient, letter, seal, divider, onContinue }: PreviewChapterProps) {
  const { salutation, body } = useMemo(() => splitSalutation(letter), [letter]);

  const excerpt = body.length > EXCERPT_LENGTH ? `${body.slice(0, EXCERPT_LENGTH).trimEnd()}…` : body;

  return (
    <section
      aria-label={`Prévia da carta para ${recipient}`}
      className="mv-bg-soft relative flex min-h-full w-full flex-col overflow-hidden px-5 pb-10 pt-10 sm:items-center sm:justify-center"
    >
      <p className="mv-label mv-rise mb-6 w-full max-w-xl px-3">Prévia</p>

      <article className="mv-glass mv-rise flex w-full max-w-xl flex-col px-7 py-9 sm:px-10" style={{ "--mv-delay": "120ms" } as React.CSSProperties}>
        {/* Envelope com o selo do tema (coração no Flores). */}
        <div aria-hidden="true" className="relative h-14 w-20 rounded-md bg-[#fff3f8] shadow-[4px_6px_0_rgba(0,0,0,0.18)]">
          <svg viewBox="0 0 80 56" className="absolute inset-0 h-full w-full">
            <path d="M2 4 40 32 78 4M2 54 30 28M78 54 50 28" fill="none" stroke="var(--mv-accent)" strokeOpacity="0.5" strokeWidth="1.2" />
          </svg>
          <span className="absolute left-1/2 top-1/2 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 border-(--mv-accent) bg-[#fff3f8]">
            <ThemeGlyph kind={seal} className="h-5 w-5" />
          </span>
        </div>

        <h1 className="mv-serif mt-8 text-[2.1rem] leading-tight text-(--mv-text)">
          Uma carta para
          <span className="block wrap-break-word text-[3.25rem] italic leading-[1.05] text-(--mv-accent-soft)">{recipient}</span>
        </h1>

        <div aria-hidden="true" className="mv-divider my-6 max-w-[60%]">
          <ThemeGlyph kind={divider} className="h-5 w-5" />
        </div>

        {excerpt && (
          <div className="mv-fade-out mv-serif max-h-[19rem] overflow-hidden text-[1.25rem] leading-[1.75] text-(--mv-text)">
            {salutation && <p className="italic text-(--mv-accent)">{salutation}</p>}
            <p className="whitespace-pre-wrap wrap-anywhere">{excerpt}</p>
          </div>
        )}

        <div className="mt-8">
          <button type="button" onClick={onContinue} className="mv-pill">
            Ler carta completa <span aria-hidden="true">→</span>
          </button>
        </div>
      </article>
    </section>
  );
}
