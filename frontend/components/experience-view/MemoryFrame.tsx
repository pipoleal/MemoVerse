"use client";

import { forwardRef, type ReactNode } from "react";
import { motion } from "framer-motion";

type MemoryFrameProps = {
  // Posição desta memória entre TODAS as memórias (fotos e depois vídeos),
  // começando em 0 — só para exibição (barras, "Memória 01", "01 / 05").
  // Não confundir com o `index` de Photo/VideoMemoryBeat, que continua
  // sendo a posição dentro de photos[]/videos[] para renovar a URL.
  memoryNumber: number;
  memoryCount: number;
  caption?: string;
  ariaLabel: string;
  // Rola o MemoriesCanvas até o slide `slide` (0 = Cena, 1 = 1ª memória).
  onNavigate: (slide: number) => void;
  // false até a memória chegar perto da tela (lazy mount em
  // Photo/VideoMemoryBeat) — a moldura e a legenda só montam depois.
  isNear: boolean;
  // Vídeo já tocando: o contador sairia por cima dos controles nativos.
  hideCounter?: boolean;
  children: ReactNode;
};

// Acima disso os pontos clicáveis ficam apertados demais no celular — as
// barras de progresso do topo continuam mostrando a posição.
const MAX_DOTS = 12;

function pad(value: number) {
  return String(value).padStart(2, "0");
}

// Estrutura comum das telas de Foto/Vídeo do redesign: barras de progresso,
// rótulo "Memória 01", moldura arredondada (o conteúdo vem de `children`),
// contador "01 / 05", legenda em cartão de vidro, pontos de navegação e
// "Deslize para a próxima" / "Fim das memórias".
const MemoryFrame = forwardRef<HTMLElement, MemoryFrameProps>(function MemoryFrame(
  { memoryNumber, memoryCount, caption, ariaLabel, onNavigate, isNear, hideCounter = false, children },
  ref
) {
  const isLast = memoryNumber === memoryCount - 1;

  return (
    <section
      ref={ref}
      aria-label={ariaLabel}
      className="mv-bg-vivid relative flex flex-1 flex-col items-center px-5 pb-5 pt-5 sm:px-8"
    >
      <div aria-hidden="true" className="flex w-full max-w-md gap-1.5">
        {Array.from({ length: memoryCount }, (_, i) => (
          <span
            key={i}
            className={`h-[3px] flex-1 rounded-full ${i <= memoryNumber ? "bg-white/90" : "bg-white/25"}`}
          />
        ))}
      </div>

      <p className="mv-label mt-5 text-(--mv-text) opacity-85">Memória {pad(memoryNumber + 1)}</p>

      {isNear && (
        <>
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative mt-5 min-h-[16rem] w-full max-w-md flex-1 overflow-hidden rounded-[28px] border border-white/25 bg-black/30 shadow-[0_30px_80px_rgba(0,0,0,0.4)]"
          >
            {children}

            {!hideCounter && (
              <span className="mv-label pointer-events-none absolute bottom-4 right-4 rounded-full border border-white/15 bg-black/45 px-4 py-1.5 text-white backdrop-blur-sm">
                {pad(memoryNumber + 1)} / {pad(memoryCount)}
              </span>
            )}
          </motion.div>

          {/* Legenda individual (Fase 2.2) — irmã abaixo da moldura, nunca
              sobreposta à foto; sem texto, nenhum espaço é reservado.
              Legendas longas rolam dentro do cartão em vez de empurrar a
              moldura para fora da tela. */}
          {caption && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
              className="mv-glass mt-5 max-h-36 w-full max-w-md overflow-y-auto rounded-[24px] px-6 py-4 text-center"
            >
              <p className="mv-serif wrap-anywhere text-[1.3rem] italic leading-snug text-(--mv-text)">
                {caption}
              </p>
            </motion.div>
          )}
        </>
      )}

      {memoryCount > 1 && memoryCount <= MAX_DOTS && (
        <div className="mt-5 flex items-center gap-1">
          {Array.from({ length: memoryCount }, (_, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onNavigate(i + 1)}
              aria-label={`Ir para a memória ${i + 1}`}
              aria-current={i === memoryNumber ? "true" : undefined}
              className="mv-focus flex h-6 items-center justify-center rounded-full px-1"
            >
              <span
                className={`block h-2 rounded-full transition-[width,background-color] duration-300 ${
                  i === memoryNumber ? "w-8 bg-white" : "w-2 bg-white/40"
                }`}
              />
            </button>
          ))}
        </div>
      )}

      {isLast ? (
        <p className="mv-label mt-3 py-2">Fim das memórias</p>
      ) : (
        <button
          type="button"
          onClick={() => onNavigate(memoryNumber + 2)}
          className="mv-label mv-focus mt-3 rounded-full px-3 py-2"
        >
          Deslize para a próxima
        </button>
      )}
    </section>
  );
});

export default MemoryFrame;
