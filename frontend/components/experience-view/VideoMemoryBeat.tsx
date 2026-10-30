"use client";

import { useRef, useState } from "react";

import { useInViewport } from "@/lib/useInViewport";
import { fetchPublicExperience, toExperience } from "@/lib/publicExperience";

import MemoryFrame from "./MemoryFrame";

type VideoMemoryBeatProps = {
  src: string;
  // Fase 2.2 (estendida a vídeo): opcional — "" (ou ausente) não reserva
  // nenhum espaço visual, mesmo padrão de PhotoMemoryBeat.tsx.
  caption?: string;
  // Posição dentro de videos[] — usada para achar a URL renovada abaixo.
  index: number;
  // Ver os mesmos parâmetros em PhotoMemoryBeat.tsx.
  memoryNumber: number;
  memoryCount: number;
  onNavigate: (slide: number) => void;
  // Ver o mesmo parâmetro em PhotoMemoryBeat.tsx — usado aqui pela mesma
  // razão (renovar a URL assinada se ela expirar antes do clique em play).
  slug?: string;
};

export default function VideoMemoryBeat({
  src,
  caption,
  index,
  memoryNumber,
  memoryCount,
  onNavigate,
  slug,
}: VideoMemoryBeatProps) {
  const sectionRef = useRef<HTMLElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const { isInView: isNear } = useInViewport<HTMLElement>(
    { rootMargin: "55% 0px", threshold: 0, once: true },
    sectionRef
  );

  // Vídeo só toca quando o visitante clica — nunca sozinho ao entrar na
  // viewport. Antes disso tocava automaticamente (mudo) a partir de 60% de
  // visibilidade: mesmo mudo, iniciar a reprodução de um <video> rouba o
  // foco de áudio da sessão em navegadores mobile (Safari/iOS em
  // particular), pausando a música de fundo (YouTube/Spotify/Apple Music
  // em MusicPlayer.tsx) sem nenhuma ação do visitante — o próprio bug
  // relatado. Reproduzir só a partir de um clique explícito evita esse
  // roubo de foco automático.
  const [hasStarted, setHasStarted] = useState(false);

  const [currentSrc, setCurrentSrc] = useState(src);
  const hasRetriedRef = useRef(false);

  async function handleVideoError() {
    if (hasRetriedRef.current || !slug) return;
    hasRetriedRef.current = true;

    try {
      const fresh = await fetchPublicExperience(slug);
      const renewedUrl = toExperience(fresh).videos[index]?.url;
      if (renewedUrl) setCurrentSrc(renewedUrl);
    } catch {
      // Sem conexão ou slug não encontra mais a experiência — o vídeo
      // continua quebrado, mesmo estado de antes desta mudança.
    }
  }

  function handlePlayClick() {
    const video = videoRef.current;
    if (!video) return;
    video.play().catch(() => {
      // Bloqueado pelo navegador apesar do clique (raro) — os controles
      // nativos, já visíveis a partir daqui, continuam disponíveis.
    });
    setHasStarted(true);
  }

  return (
    <MemoryFrame
      ref={sectionRef}
      ariaLabel={`Memória ${memoryNumber + 1} de ${memoryCount} (vídeo)`}
      memoryNumber={memoryNumber}
      memoryCount={memoryCount}
      caption={caption}
      onNavigate={onNavigate}
      isNear={isNear}
      hideCounter={hasStarted}
    >
      {/* object-contain (em vez de object-cover): vídeo vertical gravado no
          celular não fica cortado pra caber na moldura — sobra o fundo
          escuro translúcido da moldura, em vez de perder pedaço do quadro.
          controls só aparece depois do primeiro clique — antes disso o
          botão de play abaixo é o único controle visível, pra não duplicar
          (nosso botão + o de play nativo). */}
      <video
        ref={videoRef}
        src={currentSrc}
        loop
        playsInline
        controls={hasStarted}
        preload="metadata"
        onError={handleVideoError}
        className="absolute inset-0 h-full w-full object-contain"
      />

      {!hasStarted && (
        <button
          type="button"
          onClick={handlePlayClick}
          aria-label="Reproduzir vídeo"
          className="mv-focus absolute inset-0 flex items-center justify-center bg-black/20 transition-colors hover:bg-black/5"
        >
          <span className="flex h-16 w-16 items-center justify-center rounded-full border border-(--mv-accent) bg-white/15 text-white shadow-lg backdrop-blur-md transition-transform hover:scale-105">
            <svg viewBox="0 0 24 24" fill="currentColor" className="ml-1 h-7 w-7">
              <path d="M8 5v14l11-7z" />
            </svg>
          </span>
        </button>
      )}
    </MemoryFrame>
  );
}
