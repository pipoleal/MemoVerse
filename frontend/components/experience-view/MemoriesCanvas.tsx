"use client";

import { useEffect, useRef } from "react";

import MemoryPreludeChapter from "./scenes/MemoryPreludeChapter";
import PhotoMemoryBeat from "./PhotoMemoryBeat";
import VideoMemoryBeat from "./VideoMemoryBeat";
import { useInViewport } from "@/lib/useInViewport";

type MemoriesCanvasProps = {
  shortMessage: string;
  photos: string[];
  videos: string[];
  onComplete: () => void;
};

const EMPTY_MEMORIES_DELAY = 4200;

export default function MemoriesCanvas({
  shortMessage,
  photos,
  videos,
  onComplete,
}: MemoriesCanvasProps) {
  const hasMedia = photos.length > 0 || videos.length > 0;
  const completedRef = useRef(false);

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

  return (
    <div className="memories-scroll absolute inset-0 overflow-y-auto overflow-x-hidden bg-[#02040a]">
      <MemoryPreludeChapter message={shortMessage} />

      {photos.map((photo, index) => (
        <PhotoMemoryBeat key={`photo-${index}`} src={photo} index={index} total={photos.length} />
      ))}

      {videos.map((video, index) => (
        <VideoMemoryBeat key={`video-${index}`} src={video} index={index} total={videos.length} />
      ))}

      {hasMedia && <div ref={sentinelRef} aria-hidden="true" className="h-24 w-full" />}

      <style jsx>{`
        /* Esconde a barra de scroll visualmente, mantendo overflow-y:auto funcional. */
        .memories-scroll {
          scrollbar-width: none; /* Firefox */
          -ms-overflow-style: none; /* IE/Edge legado */
        }

        .memories-scroll::-webkit-scrollbar {
          display: none; /* Chrome, Edge (Chromium), Safari */
        }
      `}</style>
    </div>
  );
}
