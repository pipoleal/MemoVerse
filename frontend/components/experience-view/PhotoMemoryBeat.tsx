"use client";

import { useRef } from "react";
import Image from "next/image";
import { motion, useScroll, useTransform } from "framer-motion";

import { useInViewport } from "@/lib/useInViewport";
import { DEFAULT_THEME_CODE, THEME_REGISTRY, type ThemeVisual } from "@/lib/themeRegistry";

type PhotoMemoryBeatProps = {
  // Opcional com fallback pro tema padrão — mesmo padrão de
  // VideoMemoryBeat.tsx (o outro "beat" de MemoriesCanvas.tsx). Estilo da
  // legenda (abaixo) vem daqui: nunca uma cor genérica fixa, sempre a
  // identidade visual do tema escolhido pelo dono da experiência.
  theme?: ThemeVisual;
  src: string;
  // Fase 2.2: opcional — "" (ou ausente) não reserva nenhum espaço visual,
  // a foto renderiza exatamente como antes desta mudança.
  caption?: string;
  index: number;
  total: number;
};

type Composition = {
  align: "center" | "left" | "right";
  rotate: number;
  aspect: string;
  glowClass: string;
  glowColor: string;
  parallaxRange: [number, number];
};

/*
 * Pequeno conjunto de composições que se repete ciclicamente (index % length).
 * Não é "10 layouts diferentes" — é uma variação natural sobre a mesma
 * linguagem visual (vinheta escura, brilho ambiente, poeira estelar).
 */
const COMPOSITIONS: Composition[] = [
  {
    align: "center",
    rotate: 0,
    aspect: "aspect-[4/5]",
    glowClass: "left-1/2 top-0 -translate-x-1/2 -translate-y-1/3",
    glowColor: "bg-indigo-400/20",
    parallaxRange: [30, -30],
  },
  {
    align: "left",
    rotate: -2,
    aspect: "aspect-[3/4]",
    glowClass: "-left-16 top-1/4",
    glowColor: "bg-amber-300/15",
    parallaxRange: [42, -18],
  },
  {
    align: "right",
    rotate: 2,
    aspect: "aspect-[3/4]",
    glowClass: "-right-16 bottom-1/4",
    glowColor: "bg-cyan-300/15",
    parallaxRange: [18, -42],
  },
  {
    align: "center",
    rotate: 0,
    aspect: "aspect-video",
    glowClass: "left-1/2 bottom-0 -translate-x-1/2 translate-y-1/3",
    glowColor: "bg-rose-300/15",
    parallaxRange: [24, -24],
  },
];

const DUST = [
  ["18%", "22%", "0s", "2.6s"],
  ["78%", "16%", "0.6s", "3.1s"],
  ["12%", "82%", "1.1s", "2.9s"],
  ["84%", "78%", "0.4s", "3.4s"],
] as const;

export default function PhotoMemoryBeat({
  theme = THEME_REGISTRY[DEFAULT_THEME_CODE],
  src,
  caption,
  index,
  total,
}: PhotoMemoryBeatProps) {
  const sectionRef = useRef<HTMLDivElement | null>(null);

  const { isInView: isNear } = useInViewport<HTMLDivElement>(
    { rootMargin: "55% 0px", threshold: 0, once: true },
    sectionRef
  );

  const composition = COMPOSITIONS[index % COMPOSITIONS.length];

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start end", "end start"],
  });

  const imageY = useTransform(scrollYProgress, [0, 1], composition.parallaxRange);
  const glowY = useTransform(
    scrollYProgress,
    [0, 1],
    [composition.parallaxRange[0] * 0.4, composition.parallaxRange[1] * 0.4]
  );

  const justify =
    composition.align === "left"
      ? "justify-start"
      : composition.align === "right"
        ? "justify-end"
        : "justify-center";

  return (
    <section
      ref={sectionRef}
      aria-label={`Memória ${index + 1} de ${total}`}
      className="relative flex min-h-screen w-full items-center overflow-hidden px-6 py-24 sm:px-12"
    >
      <motion.div
        aria-hidden="true"
        style={{ y: glowY }}
        className={`pointer-events-none absolute h-72 w-72 rounded-full blur-3xl ${composition.glowClass} ${composition.glowColor}`}
      />

      {DUST.map(([left, top, delay, duration], dustIndex) => (
        <span
          key={`${left}-${top}`}
          aria-hidden="true"
          className="star pointer-events-none absolute h-1 w-1 rounded-full bg-white/70"
          style={{
            left,
            top,
            animationDelay: delay,
            animationDuration: duration,
            opacity: dustIndex % 2 === 0 ? 0.6 : 0.4,
          }}
        />
      ))}

      <div className={`relative flex w-full ${justify}`}>
        {isNear && (
          <div className="flex w-full max-w-xl flex-col items-center gap-8">
            <motion.div
              initial={{ opacity: 0, scale: 0.94, filter: "blur(6px)" }}
              whileInView={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.9, ease: "easeOut" }}
              style={{ y: imageY, rotate: composition.rotate }}
              className={`relative w-full overflow-hidden rounded-[2rem] border border-white/10 shadow-[0_30px_100px_rgba(0,0,0,0.55)] ${composition.aspect}`}
            >
              <motion.div
                className="relative h-full w-full"
                animate={{ scale: [1, 1.06] }}
                transition={{ duration: 11, repeat: Infinity, repeatType: "mirror", ease: "easeInOut" }}
              >
                <Image
                  src={src}
                  alt={`Memória ${index + 1}`}
                  fill
                  unoptimized
                  sizes="(max-width: 768px) 100vw, 640px"
                  className="object-cover"
                />
              </motion.div>

              <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-black/50 via-transparent to-black/10" />

              <span className="pointer-events-none absolute bottom-4 right-5 text-xs font-medium uppercase tracking-[0.3em] text-white/50">
                {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
              </span>
            </motion.div>

            {/* Fase 2.2: legenda individual — nunca sobreposta à foto (é uma
                irmã abaixo, não um overlay), e nunca uma legenda genérica de
                galeria: pertence só a esta foto. Sem texto, nenhum espaço
                extra é reservado.
                Cartão com a mesma linguagem do tema escolhido (ornamentClass/
                textClass, os mesmos tokens que LetterChapter já usa) — nunca
                mais um texto solto colado embaixo da foto, sem contraste com
                o fundo. gap-6 acima (era gap-4) dá o respiro entre foto e
                legenda que faltava. */}
            {caption && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: 0.8, delay: 0.25, ease: "easeOut" }}
                className={`w-fit max-w-[85%] rounded-2xl border px-6 py-4 text-center backdrop-blur-sm ${theme.letter.ornamentClass}`}
              >
                <p
                  className={`wrap-anywhere text-sm italic leading-relaxed sm:text-base ${theme.letter.textClass}`}
                >
                  {caption}
                </p>
              </motion.div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
