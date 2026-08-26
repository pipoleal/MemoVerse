"use client";

import { useEffect, useRef, useState } from "react";
import YouTube from "react-youtube";

// Mesmo vídeo enviado para a landing de lançamento — loop de verdade no
// YouTube exige playerVars.loop=1 JUNTO de playlist apontando pro mesmo
// videoId (peculiaridade documentada da própria API: loop sozinho não
// repete um vídeo avulso, só uma playlist).
const VIDEO_ID = "Tx9zMFodNtA";

// Mesmo padrão de tipo mínimo já usado em MusicPlayer.tsx (nunca importa
// o tipo real de react-youtube) — só os três métodos que este componente
// de fato chama.
type MinimalPlayer = {
  playVideo: () => void;
  mute: () => void;
  unMute: () => void;
};

// Autoplay COM som é bloqueado por todo navegador moderno sem interação
// prévia do visitante — não existe forma de contornar isso de fora do
// próprio navegador. autoplay + mute juntos é a única combinação que
// reproduz de verdade assim que a página abre (documentado pela própria
// política de autoplay do Chrome/Safari/Firefox); a partir do primeiro
// clique/toque/tecla em QUALQUER lugar da página, o som é ligado
// automaticamente — na prática, toca desde a abertura e fica audível no
// primeiro gesto do visitante, o mais próximo do pedido que o navegador
// permite. O botão no canto sempre deixa a pessoa silenciar de volta.
export default function LaunchMusicPlayer() {
  const playerRef = useRef<MinimalPlayer | null>(null);
  const [muted, setMuted] = useState(true);

  useEffect(() => {
    function unmuteOnFirstInteraction() {
      if (playerRef.current) {
        playerRef.current.unMute();
        playerRef.current.playVideo();
        setMuted(false);
      }
      window.removeEventListener("pointerdown", unmuteOnFirstInteraction);
      window.removeEventListener("keydown", unmuteOnFirstInteraction);
    }

    window.addEventListener("pointerdown", unmuteOnFirstInteraction);
    window.addEventListener("keydown", unmuteOnFirstInteraction);

    return () => {
      window.removeEventListener("pointerdown", unmuteOnFirstInteraction);
      window.removeEventListener("keydown", unmuteOnFirstInteraction);
    };
  }, []);

  function toggleMute() {
    if (!playerRef.current) return;

    if (muted) {
      playerRef.current.unMute();
      playerRef.current.playVideo();
      setMuted(false);
    } else {
      playerRef.current.mute();
      setMuted(true);
    }
  }

  return (
    <>
      <div className="pointer-events-none fixed -left-250 -top-250 h-px w-px overflow-hidden opacity-0">
        <YouTube
          videoId={VIDEO_ID}
          opts={{
            width: "1",
            height: "1",
            playerVars: {
              autoplay: 1,
              mute: 1,
              controls: 0,
              playsinline: 1,
              rel: 0,
              loop: 1,
              playlist: VIDEO_ID,
            },
          }}
          onReady={(event) => {
            playerRef.current = event.target;
            event.target.playVideo();
          }}
        />
      </div>

      <button
        type="button"
        onClick={toggleMute}
        aria-label={muted ? "Ativar som" : "Silenciar"}
        aria-pressed={!muted}
        className="pointer-events-auto fixed bottom-4 right-4 z-20 flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5 text-lg text-white backdrop-blur-xl transition hover:bg-white/10"
      >
        <span aria-hidden="true">{muted ? "🔇" : "🔊"}</span>
      </button>
    </>
  );
}
