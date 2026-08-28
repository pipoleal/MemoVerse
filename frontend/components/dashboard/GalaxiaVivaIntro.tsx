"use client";

import { useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";

// Introdução em vídeo antes da tela da Galáxia Viva. O arquivo (mesmo
// vídeo de frontend/app/login/galaxia.mp4) foi enviado ao bucket R2 de
// produção pelo dono do produto para reduzir o peso do bundle — este
// componente pede a URL assinada (temporária) ao backend
// (GET /experiences/galaxy-intro-video/, ver apps.experiences.views.
// GalaxyIntroVideoView) em vez de apontar pra um arquivo estático local.
// autoPlay exige muted (política de autoplay de todo navegador moderno,
// mesmo motivo documentado em LaunchMusicPlayer.tsx); o botão de som
// deixa ativar áudio a partir de um gesto real do usuário.
//
// Transição: GalaxiaVivaView já monta o GalaxiaViva (com suas próprias
// estrelas que brilham/se mecham) POR BAIXO deste overlay desde o início —
// nunca uma segunda implementação de céu estrelado aqui. "Pular introdução"
// e o fim do vídeo (onEnded) levam ao mesmo lugar: um fade (opacity,
// 700ms) que revela o que já está rodando por baixo, em vez de um corte
// seco pra preto.
type GalaxiaVivaIntroProps = {
  onFinish: () => void;
};

const FADE_MS = 700;

export default function GalaxiaVivaIntro({ onFinish }: GalaxiaVivaIntroProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [muted, setMuted] = useState(true);
  const [fading, setFading] = useState(false);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);

  // Roda uma única vez (montagem/desmontagem deste overlay, nunca a cada
  // re-render de GalaxiaVivaView) — a URL assinada expira, então nunca é
  // cacheada/reaproveitada entre visitas. Vídeo indisponível (R2 não
  // configurado, rede, 404) nunca trava a tela: pula a introdução
  // silenciosamente, igual a "Pular introdução".
  useEffect(() => {
    let cancelled = false;
    api
      .get<{ url: string }>("/experiences/galaxy-intro-video/")
      .then((response) => {
        if (!cancelled) setVideoUrl(response.data.url);
      })
      .catch(() => {
        if (!cancelled) onFinish();
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function beginFadeOut() {
    if (fading) return;
    setFading(true);
    window.setTimeout(onFinish, FADE_MS);
  }

  function toggleMute() {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setMuted(video.muted);
  }

  return (
    <div
      className={`fixed inset-0 z-50 flex items-center justify-center bg-black transition-opacity ease-in-out ${
        fading ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
      style={{ transitionDuration: `${FADE_MS}ms` }}
    >
      {videoUrl && (
        <video
          ref={videoRef}
          src={videoUrl}
          autoPlay
          muted
          playsInline
          onEnded={beginFadeOut}
          onError={beginFadeOut}
          className="h-full w-full object-cover"
        />
      )}

      <button
        type="button"
        onClick={toggleMute}
        aria-label={muted ? "Ativar som" : "Silenciar"}
        aria-pressed={!muted}
        className="pointer-events-auto absolute bottom-6 right-6 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-black/40 text-lg text-white backdrop-blur-xl transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-300"
      >
        <span aria-hidden="true">{muted ? "🔇" : "🔊"}</span>
      </button>

      <button
        type="button"
        onClick={beginFadeOut}
        className="pointer-events-auto absolute bottom-6 left-6 z-10 rounded-full border border-white/15 bg-black/40 px-5 py-2.5 text-sm font-semibold text-white backdrop-blur-xl transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-300"
      >
        Pular introdução
      </button>
    </div>
  );
}
