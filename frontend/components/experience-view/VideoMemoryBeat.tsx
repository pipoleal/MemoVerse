"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";

import { useInViewport } from "@/lib/useInViewport";

type VideoMemoryBeatProps = {
  src: string;
  index: number;
  total: number;
};

export default function VideoMemoryBeat({ src, index, total }: VideoMemoryBeatProps) {
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
      className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-black px-6 py-24"
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(20,30,60,0.25),transparent_60%)]" />

      {isNear && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="relative aspect-video w-full max-w-3xl overflow-hidden rounded-[1.5rem] border border-white/10 shadow-[0_30px_120px_rgba(0,0,0,0.6)]"
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
      )}
    </section>
  );
}
