"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

import { useInViewport } from "@/lib/useInViewport";
import { DEFAULT_THEME_CODE, THEME_REGISTRY, type ThemeVisual } from "@/lib/themeRegistry";

type VideoMemoryBeatProps = {
  theme?: ThemeVisual;
  src: string;
  // Fase 2.2 (estendida a vídeo): opcional — "" (ou ausente) não reserva
  // nenhum espaço visual, mesmo padrão de PhotoMemoryBeat.tsx.
  caption?: string;
  index: number;
  total: number;
};

export default function VideoMemoryBeat({
  theme = THEME_REGISTRY[DEFAULT_THEME_CODE],
  src,
  caption,
  index,
  total,
}: VideoMemoryBeatProps) {
  const sectionRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const { isInView: isNear } = useInViewport<HTMLDivElement>(
    { rootMargin: "55% 0px", threshold: 0, once: true },
    sectionRef
  );

  const { isInView: isPlaying } = useInViewport<HTMLDivElement>(
    { rootMargin: "0px", threshold: 0.6 },
    sectionRef
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.play().catch(() => {
        // autoplay pode ser bloqueado pelo navegador; os controles nativos continuam disponíveis.
      });
    } else {
      video.pause();
    }
  }, [isPlaying]);

  return (
    <section
      ref={sectionRef}
      aria-label={`Vídeo ${index + 1} de ${total}`}
      className={`relative flex min-h-screen w-full items-center justify-center overflow-hidden px-6 py-24 ${theme.gradient}`}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(20,30,60,0.25),transparent_60%)]" />

      {isNear && (
        <div className="flex w-full max-w-5xl flex-col items-center gap-8">
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative aspect-video w-full overflow-hidden rounded-[1.5rem] border border-white/10 shadow-[0_30px_120px_rgba(0,0,0,0.6)]"
          >
            <video
              ref={videoRef}
              src={src}
              muted
              loop
              playsInline
              controls
              preload="metadata"
              className="h-full w-full object-cover"
            />

            <span className="pointer-events-none absolute bottom-4 right-5 text-xs font-medium uppercase tracking-[0.3em] text-white/50">
              {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
            </span>
          </motion.div>

          {/* Mesma linguagem visual da legenda de PhotoMemoryBeat.tsx —
              nunca sobreposta ao vídeo, sem texto não reserva espaço. */}
          {caption && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.8, delay: 0.25, ease: "easeOut" }}
              className={`w-fit max-w-[85%] rounded-2xl border px-8 py-5 text-center backdrop-blur-sm ${theme.letter.ornamentClass}`}
            >
              <p className={`wrap-anywhere text-sm italic leading-loose tracking-wide sm:text-base ${theme.letter.textClass}`}>
                {caption}
              </p>
            </motion.div>
          )}
        </div>
      )}
    </section>
  );
}
