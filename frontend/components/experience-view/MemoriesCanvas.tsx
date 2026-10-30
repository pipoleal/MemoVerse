"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import MemoryPreludeChapter from "./scenes/MemoryPreludeChapter";
import PhotoMemoryBeat from "./PhotoMemoryBeat";
import VideoMemoryBeat from "./VideoMemoryBeat";
import { useInViewport } from "@/lib/useInViewport";
import type { PhotoMemory, VideoMemory } from "@/components/experience/types";

type MemoriesCanvasProps = {
  shortMessage: string;
  // Usados só pela Cena (MemoryPreludeChapter): nome na órbita e ano ao
  // fundo.
  recipient: string;
  eventDate: string;
  // Fase 2.2: cada foto/vídeo carrega sua própria legenda opcional.
  photos: PhotoMemory[];
  videos: VideoMemory[];
  // undefined no modo wizard/preview (sem link público ainda) — nesse caso
  // PhotoMemoryBeat/VideoMemoryBeat simplesmente não tentam renovar a URL
  // assinada se ela expirar (ver o comentário sobre isso em ambos).
  slug?: string;
  onComplete: () => void;
};

// Sem mídia nenhuma a Cena é a única tela — tempo suficiente para ler a
// mensagem curta antes de seguir (antes eram 4,2s, mas a mensagem só
// aparecia aos 4,6s e nunca chegava a ser vista nesse caso).
const EMPTY_MEMORIES_DELAY = 7000;

// Cada slide (Cena + uma memória por foto/vídeo) ocupa uma tela inteira e
// o scroll "encaixa" em cada um (scroll-snap): no celular, deslizar leva
// sempre exatamente para a próxima memória.
const SLIDE_CLASS = "flex min-h-full snap-start snap-always flex-col";

export default function MemoriesCanvas({
  shortMessage,
  recipient,
  eventDate,
  photos,
  videos,
  slug,
  onComplete,
}: MemoriesCanvasProps) {
  const hasMedia = photos.length > 0 || videos.length > 0;
  const memoryCount = photos.length + videos.length;
  const completedRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [activeSlide, setActiveSlide] = useState(0);

  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const { isInView: sentinelReached } = useInViewport<HTMLDivElement>(
    { rootMargin: "0px", threshold: 0.4 },
    sentinelRef
  );

  // Sem nenhuma mídia: não há o que rolar, então avança sozinho.
  useEffect(() => {
    if (completedRef.current || hasMedia) return;

    const timer = window.setTimeout(() => {
      completedRef.current = true;
      onComplete();
    }, EMPTY_MEMORIES_DELAY);

    return () => window.clearTimeout(timer);
  }, [hasMedia, onComplete]);

  // Com mídia: avança quando a sentinela do fim do scroll entra em viewport.
  useEffect(() => {
    if (completedRef.current || !hasMedia || !sentinelReached) return;
    completedRef.current = true;
    onComplete();
  }, [hasMedia, sentinelReached, onComplete]);

  // Slide atual, só para o indicador lateral da Cena — calculado a partir
  // do scrollTop (um setState só quando muda), nunca um observer por slide.
  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;

    let frame = 0;
    function handleScroll() {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!container) return;
        setActiveSlide(Math.round(container.scrollTop / Math.max(container.clientHeight, 1)));
      });
    }

    container.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      container.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Navegação por clique (pontos, "Deslize para a próxima", indicador
  // lateral) — mesmo destino que o deslize do dedo.
  const goToSlide = useCallback((slide: number) => {
    const container = scrollRef.current;
    const target = container?.querySelector<HTMLElement>(`[data-mv-slide="${slide}"]`);
    if (!container || !target) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    container.scrollTo({ top: target.offsetTop, behavior: reduceMotion ? "auto" : "smooth" });
  }, []);

  return (
    <div className="absolute inset-0">
      <div ref={scrollRef} className="mv-no-scrollbar absolute inset-0 snap-y snap-mandatory overflow-y-auto overflow-x-hidden bg-(--mv-night)">
        <div data-mv-slide={0} className={SLIDE_CLASS}>
          <MemoryPreludeChapter message={shortMessage} recipient={recipient} eventDate={eventDate} hasMedia={hasMedia} />
        </div>

        {photos.map((photo, index) => (
          <div key={`photo-${index}`} data-mv-slide={index + 1} className={SLIDE_CLASS}>
            <PhotoMemoryBeat
              src={photo.url}
              caption={photo.caption}
              index={index}
              memoryNumber={index}
              memoryCount={memoryCount}
              onNavigate={goToSlide}
              slug={slug}
            />
          </div>
        ))}

        {videos.map((video, index) => (
          <div key={`video-${index}`} data-mv-slide={photos.length + index + 1} className={SLIDE_CLASS}>
            <VideoMemoryBeat
              src={video.url}
              caption={video.caption}
              index={index}
              memoryNumber={photos.length + index}
              memoryCount={memoryCount}
              onNavigate={goToSlide}
              slug={slug}
            />
          </div>
        ))}

        {/* snap-end: com snap obrigatório, a sentinela também precisa ser
            um ponto de encaixe, senão o scroll nunca chegaria até ela. */}
        {hasMedia && <div ref={sentinelRef} aria-hidden="true" className="h-24 w-full snap-end" />}
      </div>

      {/* Indicador lateral da Cena (um ponto por tela) — some ao entrar nas
          memórias, que já têm barras de progresso próprias. */}
      {hasMedia && memoryCount <= 12 && (
        <nav
          aria-label="Telas das memórias"
          className={`absolute right-3 top-1/2 z-10 flex -translate-y-1/2 flex-col gap-1 transition-opacity duration-500 ${
            activeSlide === 0 ? "opacity-100" : "pointer-events-none opacity-0"
          }`}
        >
          {Array.from({ length: memoryCount + 1 }, (_, slide) => (
            <button
              key={slide}
              type="button"
              onClick={() => goToSlide(slide)}
              tabIndex={activeSlide === 0 ? 0 : -1}
              aria-label={slide === 0 ? "Início" : `Memória ${slide}`}
              aria-current={slide === activeSlide ? "true" : undefined}
              className="mv-focus flex h-6 w-6 items-center justify-center rounded-full"
            >
              <span
                className={`block h-1.5 w-1.5 rounded-full ${
                  slide === activeSlide ? "scale-150 bg-(--mv-accent)" : "bg-(--mv-accent-soft) opacity-40"
                }`}
              />
            </button>
          ))}
        </nav>
      )}
    </div>
  );
}
