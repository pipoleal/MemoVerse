"use client";

import { useEffect, useMemo, useState } from "react";

type ClientIntroSceneProps = {
  title?: string;
  recipient: string;
  letter: string;
  theme?: string;
  photos?: string[];
  videos?: string[];
  onComplete?: () => void;
};

type IntroPhase =
  | "star"
  | "reveal"
  | "name"
  | "letter"
  | "memories"
  | "complete";

export default function ClientIntroScene({
  title,
  recipient,
  letter,
  theme,
  photos = [],
  videos = [],
  onComplete,
}: ClientIntroSceneProps) {
  const [phase, setPhase] =
    useState<IntroPhase>("star");

  /*
   * ==========================================
   * TEMA
   * ==========================================
   */

  const themeClass = useMemo(() => {
    const normalized =
      theme?.toLowerCase().trim();

    if (
      normalized?.includes("romantic") ||
      normalized?.includes("romântico") ||
      normalized?.includes("amor")
    ) {
      return "from-black via-rose-950/20 to-black";
    }

    if (
      normalized?.includes("cinema") ||
      normalized?.includes("movie") ||
      normalized?.includes("filme")
    ) {
      return "from-black via-slate-900/30 to-black";
    }

    if (
      normalized?.includes("gold") ||
      normalized?.includes("dourado")
    ) {
      return "from-black via-yellow-950/20 to-black";
    }

    return "from-black via-slate-950/20 to-black";
  }, [theme]);

  /*
   * ==========================================
   * MEMÓRIAS
   * ==========================================
   */

  const hasPhotos =
    photos.length > 0;

  const hasVideos =
    videos.length > 0;

  const hasMemories =
    hasPhotos || hasVideos;

  /*
   * ==========================================
   * SEQUÊNCIA DA INTRODUÇÃO
   * ==========================================
   *
   * 0s
   * estrela
   *
   * 1.2s
   * brilho
   *
   * 2.8s
   * nome
   *
   * 5.2s
   * carta
   *
   * 9s
   * memórias
   *
   * 10.5s
   * final
   */

  useEffect(() => {
    const revealTimer = setTimeout(() => {
      setPhase("reveal");
    }, 1200);

    const nameTimer = setTimeout(() => {
      setPhase("name");
    }, 2800);

    const letterTimer = setTimeout(() => {
      setPhase("letter");
    }, 5200);

    const memoriesTimer = setTimeout(() => {
      if (hasMemories) {
        setPhase("memories");
      } else {
        setPhase("complete");
      }
    }, 9000);

    const completeTimer = setTimeout(() => {
      setPhase("complete");

      if (onComplete) {
        onComplete();
      }
    }, 10500);

    return () => {
      clearTimeout(revealTimer);
      clearTimeout(nameTimer);
      clearTimeout(letterTimer);
      clearTimeout(memoriesTimer);
      clearTimeout(completeTimer);
    };

    // A sequência deve ser iniciada apenas
    // quando a cena for montada.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /*
   * ==========================================
   * ESTADOS VISUAIS
   * ==========================================
   */

  /*
   * Estrela permanece apenas
   * no começo da sequência.
   */

  const showStar =
    phase === "star" ||
    phase === "reveal";

  /*
   * O nome aparece somente
   * durante a fase do nome.
   */

  const showName =
    phase === "name";

  /*
   * A carta aparece depois
   * que o nome termina.
   */

  const showLetter =
    phase === "letter" ||
    phase === "memories" ||
    phase === "complete";

  /*
   * Memórias aparecem depois
   * da carta.
   */

  const showMemories =
    phase === "memories" ||
    phase === "complete";

  return (
    <section
      className={`
        absolute
        inset-0
        z-50
        overflow-hidden
        bg-linear-to-b
        ${themeClass}
        text-white
      `}
    >

      {/* =========================================
          BRILHO CENTRAL
          ========================================= */}

      <div
        className={`
          pointer-events-none
          absolute
          left-1/2
          top-1/2
          -translate-x-1/2
          -translate-y-1/2
          rounded-full
          bg-white
          transition-all
          ease-out
          ${
            showStar
              ? "h-2 w-2 scale-100 opacity-100 duration-1000"
              : "h-3 w-3 scale-[4] opacity-0 duration-2200"
          }
        `}
        style={{
          boxShadow:
            "0 0 12px 4px rgba(255,255,255,0.9), 0 0 45px 18px rgba(255,255,255,0.45), 0 0 120px 50px rgba(120,160,255,0.18)",
        }}
      />

      {/* =========================================
          HALO
          ========================================= */}

      <div
        className={`
          pointer-events-none
          absolute
          left-1/2
          top-1/2
          -translate-x-1/2
          -translate-y-1/2
          rounded-full
          border
          border-white/10
          transition-all
          ease-out
          ${
            showStar
              ? "h-16 w-16 scale-50 opacity-0 duration-1000"
              : "h-[45vh] w-[45vh] scale-100 opacity-100 duration-2600"
          }
        `}
        style={{
          boxShadow:
            "0 0 100px 20px rgba(120,160,255,0.08)",
        }}
      />

      {/* =========================================
          CONTEÚDO PRINCIPAL
          ========================================= */}

      <div
        className="
          relative
          z-10
          flex
          min-h-full
          w-full
          flex-col
          items-center
          px-6
          text-center
        "
      >

        {/* =====================================
            NOME / TÍTULO
            ===================================== */}

        <div
          className={`
            absolute
            left-1/2
            top-1/2
            w-full
            max-w-5xl
            -translate-x-1/2
            transition-all
            duration-1800ms
            ease-out
            ${
              showName
                ? "translate-y--90px opacity-100"
                : "translate-y--50px opacity-0"
            }
          `}
        >
          <p
            className="
              text-xs
              uppercase
              tracking-[0.5em]
              text-white/45
            "
          >
            Uma história feita para
          </p>

          <h1
            className="
              mt-5
              text-5xl
              font-light
              tracking-wide
              text-white
              drop-shadow-[0_0_30px_rgba(255,255,255,0.15)]
              md:text-7xl
            "
          >
            {recipient}
          </h1>

          {title && (
            <p
              className="
                mx-auto
                mt-6
                max-w-2xl
                text-sm
                uppercase
                tracking-[0.35em]
                text-white/40
                transition-all
                duration-1000
              "
            >
              {title}
            </p>
          )}
        </div>

        {/* =====================================
            CARTA
            ===================================== */}

        <div
          className={`
            absolute
            left-1/2
            top-1/2
            w-full
            max-w-2xl
            -translate-x-1/2
            text-center
            transition-all
            duration-1800ms
            ease-out
            ${
              showLetter
                ? "translate-y-40px opacity-100"
                : "translate-y-80px opacity-0"
            }
          `}
        >
          <div
            className="
              mx-auto
              mb-8
              h-px
              w-16
              bg-white/20
            "
          />

          <p
            className="
              text-lg
              font-light
              leading-relaxed
              tracking-wide
              text-white/75
              md:text-2xl
            "
          >
            {letter}
          </p>
        </div>

      </div>

      {/* =========================================
          MEMÓRIAS
          ========================================= */}

      <div
        className={`
          absolute
          inset-0
          z-20
          flex
          items-center
          justify-center
          px-6
          transition-all
          duration-2200ms
          ease-out
          ${
            showMemories
              ? "translate-y-0 opacity-100"
              : "pointer-events-none translate-y-10 opacity-0"
          }
        `}
      >
        <div className="w-full max-w-6xl">

          {/* =====================================
              TÍTULO DAS MEMÓRIAS
              ===================================== */}

          <div className="mb-10 text-center">

            <p
              className="
                text-xs
                uppercase
                tracking-[0.45em]
                text-white/35
              "
            >
              {title || "Nossa história"}
            </p>

            <h2
              className="
                mt-4
                text-3xl
                font-light
                tracking-wide
                text-white
                md:text-5xl
              "
            >
              Algumas memórias
            </h2>

          </div>

          {/* =====================================
              FOTOS
              ===================================== */}

          {hasPhotos && (
            <div
              className="
                grid
                grid-cols-1
                gap-5
                sm:grid-cols-2
                lg:grid-cols-3
              "
            >
              {photos.map(
                (photo, index) => (
                  <div
                    key={`${photo}-${index}`}
                    className="
                      group
                      relative
                      aspect-4/3
                      overflow-hidden
                      rounded-2xl
                      border
                      border-white/10
                      bg-white/5
                      shadow-[0_20px_80px_rgba(0,0,0,0.45)]
                    "
                  >
                  <div
                    className="
                        h-full
                        w-full
                        bg-cover
                        bg-center
                        transition-transform
                        duration-1800ms
                        group-hover:scale-105
                    "
                    style={{
                        backgroundImage: `url("${photo}")`,
                    }}
                    role="img"
                    aria-label={`Memória ${index + 1}`}
                    />

                    <div
                      className="
                        pointer-events-none
                        absolute
                        inset-0
                        bg-linear-to-t
                        from-black/45
                        via-transparent
                        to-transparent
                      "
                    />
                  </div>
                )
              )}
            </div>
          )}

          {/* =====================================
              VÍDEOS
              ===================================== */}

          {hasVideos && (
            <div className="mt-8 space-y-6">

              {videos.map(
                (video, index) => (
                  <div
                    key={`${video}-${index}`}
                    className="
                      overflow-hidden
                      rounded-2xl
                      border
                      border-white/10
                      bg-black
                      shadow-[0_20px_100px_rgba(0,0,0,0.55)]
                    "
                  >
                    <video
                      src={video}
                      controls
                      playsInline
                      className="
                        max-h-[70vh]
                        w-full
                        object-contain
                      "
                    />
                  </div>
                )
              )}

            </div>
          )}

        </div>
      </div>

      {/* =========================================
          VINHETA
          ========================================= */}

      <div
        className="
          pointer-events-none
          absolute
          inset-0
          z-40
          bg-[radial-gradient(circle_at_center,transparent_20%,rgba(0,0,0,0.75)_100%)]
        "
      />

    </section>
  );
}