"use client";

import { useEffect, useMemo, useRef } from "react";
import YouTube from "react-youtube";

type MusicPlayerProps = {
  provider: string;
  url: string;
  playing: boolean;
};

function getYouTubeId(url: string) {
  try {
    const parsed = new URL(url);

    if (parsed.hostname === "youtu.be") {
      return parsed.pathname.replace("/", "");
    }

    if (
      parsed.hostname === "youtube.com" ||
      parsed.hostname === "www.youtube.com"
    ) {
      return parsed.searchParams.get("v");
    }

    return null;
  } catch {
    return null;
  }
}

// Spotify/Apple Music, ao contrário do YouTube acima, nunca ganham um
// player invisível — os dois só oferecem embed oficial visível (Spotify
// nem toca sem interação dentro do próprio iframe; Apple exige assinatura
// para tocar a faixa inteira). Ver MusicStep.tsx para o aviso equivalente
// mostrado ao criador da experiência.

// Só a forma exata /track|album|playlist/{id} (com prefixo de locale
// opcional, ex. /intl-pt/) vira embed — qualquer outro pathname em
// open.spotify.com (perfil de usuário, busca, etc.) é rejeitado, não só o
// hostname.
const SPOTIFY_PATH_PATTERN =
  /^\/(?:intl-[a-z]{2}\/)?(track|album|playlist)\/([A-Za-z0-9]+)\/?$/;

function getSpotifyEmbedUrl(url: string): string | null {
  try {
    const parsed = new URL(url);

    if (parsed.hostname.toLowerCase() !== "open.spotify.com") {
      return null;
    }

    const match = parsed.pathname.match(SPOTIFY_PATH_PATTERN);
    if (!match) {
      return null;
    }

    const [, type, id] = match;
    return `https://open.spotify.com/embed/${type}/${id}`;
  } catch {
    return null;
  }
}

// Mesma ideia: só /{country}/album|song/.../{id} (slug opcional) em
// music.apple.com vira embed. embed.music.apple.com aceita exatamente o
// mesmo pathname/query do link original — inclusive ?i=, preservado via
// parsed.search — então não há necessidade de reconstruir a URL campo a
// campo.
const APPLE_MUSIC_PATH_PATTERN =
  /^\/[a-z]{2}\/(album|song)\/(?:[^/]+\/)?\d+\/?$/i;

function getAppleMusicEmbedUrl(url: string): string | null {
  try {
    const parsed = new URL(url);

    if (parsed.hostname.toLowerCase() !== "music.apple.com") {
      return null;
    }

    if (!APPLE_MUSIC_PATH_PATTERN.test(parsed.pathname)) {
      return null;
    }

    return `https://embed.music.apple.com${parsed.pathname}${parsed.search}`;
  } catch {
    return null;
  }
}

// Alturas recomendadas pelo próprio embed oficial de cada plataforma para
// o layout compacto (capa pequena + play + progresso) — não um valor
// arbitrário nosso.
const SPOTIFY_EMBED_HEIGHT = 152;
const APPLE_MUSIC_EMBED_HEIGHT = 175;

export default function MusicPlayer({
  provider,
  url,
  playing,
}: MusicPlayerProps) {
  const playerRef = useRef<{
    playVideo: () => void;
  } | null>(null);

  const videoId = useMemo(() => {
    if (provider !== "youtube" || !url) {
      return null;
    }

    return getYouTubeId(url);
  }, [provider, url]);

  const spotifyEmbedUrl = useMemo(() => {
    if (provider !== "spotify" || !url) {
      return null;
    }

    return getSpotifyEmbedUrl(url);
  }, [provider, url]);

  const appleMusicEmbedUrl = useMemo(() => {
    if (provider !== "apple_music" || !url) {
      return null;
    }

    return getAppleMusicEmbedUrl(url);
  }, [provider, url]);

  useEffect(() => {
    if (playing && playerRef.current) {
      playerRef.current.playVideo();
    }
  }, [playing]);

  if (provider === "youtube") {
    if (!videoId) {
      return null;
    }

    return (
      <div className="pointer-events-none fixed -left-250 -top-250 h-px w-px overflow-hidden opacity-0">
        <YouTube
          videoId={videoId}
          opts={{
            width: "1",
            height: "1",
            playerVars: {
              autoplay: 0,
              controls: 0,
              playsinline: 1,
              rel: 0,
            },
          }}
          onReady={(event) => {
            playerRef.current = event.target;

            if (playing) {
              event.target.playVideo();
            }
          }}
        />
      </div>
    );
  }

  // Spotify/Apple Music só aparecem depois que a jornada começou (mesmo
  // gatilho `playing`/hasInteracted do YouTube acima) — nada de flutuar
  // sobre a tela inicial ("toque para começar") antes disso. Nenhum dos
  // dois é tocado programaticamente aqui: o próprio iframe oficial é quem
  // decide se/quando reproduz, a partir do toque do usuário nele.
  if (!playing) {
    return null;
  }

  if (provider === "spotify" && spotifyEmbedUrl) {
    return (
      <div
        className="
          pointer-events-auto
          fixed
          bottom-4
          right-4
          z-40
          w-72
          max-w-[calc(100vw-2rem)]
          overflow-hidden
          rounded-2xl
          border
          border-white/10
          bg-black/40
          shadow-[0_20px_60px_rgba(0,0,0,0.45)]
          backdrop-blur-xl
          sm:w-80
        "
      >
        <iframe
          title="Player do Spotify"
          src={spotifyEmbedUrl}
          width="100%"
          height={SPOTIFY_EMBED_HEIGHT}
          style={{ border: 0, display: "block" }}
          allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
          loading="lazy"
        />
      </div>
    );
  }

  if (provider === "apple_music" && appleMusicEmbedUrl) {
    return (
      <div
        className="
          pointer-events-auto
          fixed
          bottom-4
          right-4
          z-40
          w-72
          max-w-[calc(100vw-2rem)]
          overflow-hidden
          rounded-2xl
          border
          border-white/10
          bg-black/40
          shadow-[0_20px_60px_rgba(0,0,0,0.45)]
          backdrop-blur-xl
          sm:w-80
        "
      >
        <iframe
          title="Player do Apple Music"
          src={appleMusicEmbedUrl}
          width="100%"
          height={APPLE_MUSIC_EMBED_HEIGHT}
          style={{ border: 0, display: "block", overflow: "hidden", background: "transparent" }}
          allow="autoplay *; encrypted-media *;"
          sandbox="allow-forms allow-popups allow-same-origin allow-scripts allow-storage-access-by-user-activation allow-top-navigation-by-user-activation"
          loading="lazy"
        />
      </div>
    );
  }

  return null;
}
