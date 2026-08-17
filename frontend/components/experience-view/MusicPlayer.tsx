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

  useEffect(() => {
    if (playing && playerRef.current) {
      playerRef.current.playVideo();
    }
  }, [playing]);

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