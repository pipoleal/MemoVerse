"use client";

import { useState } from "react";

import FadeIn from "../../animations/FadeIn";
import { useExperience } from "../context/ExperienceContext";
import type { MusicProvider } from "../types";

const musicOptions: {
  id: MusicProvider;
  icon: string;
  title: string;
  description: string;
}[] = [
  {
    id: "youtube",
    icon: "▶️",
    title: "YouTube",
    description: "Escolha uma música através de um link do YouTube.",
  },
  {
    id: "spotify",
    icon: "🟢",
    title: "Spotify",
    description: "Use o link de uma música do Spotify.",
  },
  {
    id: "apple_music",
    icon: "🍎",
    title: "Apple Music",
    description: "Use o link de uma música do Apple Music.",
  },
  {
    id: "none",
    icon: "🔇",
    title: "Sem música",
    description: "Sua experiência também pode existir sem trilha sonora.",
  },
];

function getPlaceholder(provider: MusicProvider) {
  switch (provider) {
    case "youtube":
      return "https://www.youtube.com/watch?v=...";
    case "spotify":
      return "https://open.spotify.com/track/...";
    case "apple_music":
      return "https://music.apple.com/...";
    default:
      return "";
  }
}

function validateMusicUrl(
  provider: MusicProvider,
  value: string
) {
  const url = value.trim();

  if (!url) {
    return false;
  }

  try {
    const parsed = new URL(url);

    const hostname = parsed.hostname.toLowerCase();

    if (provider === "youtube") {
      return (
        hostname === "youtube.com" ||
        hostname === "www.youtube.com" ||
        hostname === "m.youtube.com" ||
        hostname === "youtu.be" ||
        hostname === "www.youtu.be"
      );
    }

    if (provider === "spotify") {
      return (
        hostname === "open.spotify.com" ||
        hostname === "spotify.com" ||
        hostname === "www.spotify.com"
      );
    }

    if (provider === "apple_music") {
      return (
        hostname === "music.apple.com" ||
        hostname === "www.music.apple.com"
      );
    }

    return false;
  } catch {
    return false;
  }
}

export default function MusicStep() {
  const { experience, updateExperience } = useExperience();

  const [selectedProvider, setSelectedProvider] =
    useState<MusicProvider>(
      experience.music?.provider ?? "none"
    );

  const [url, setUrl] = useState(
    experience.music?.url ?? ""
  );

  const [error, setError] = useState("");

  const [confirmed, setConfirmed] = useState(
    Boolean(
      experience.music?.provider !== "none" &&
        experience.music?.url
    )
  );

  function selectProvider(provider: MusicProvider) {
    setSelectedProvider(provider);
    setError("");
    setConfirmed(false);

    if (provider === "none") {
      setUrl("");

      updateExperience({
        music: {
          provider: "none",
          url: "",
        },
      });

      setConfirmed(true);

      return;
    }

    setUrl("");

    updateExperience({
      music: {
        provider,
        url: "",
      },
    });
  }

  function handleUrlChange(value: string) {
    setUrl(value);
    setError("");
    setConfirmed(false);
  }

  function confirmMusic() {
    const cleanUrl = url.trim();

    if (!cleanUrl) {
      setError("Cole o link da música primeiro.");
      setConfirmed(false);
      return;
    }

    const valid = validateMusicUrl(
      selectedProvider,
      cleanUrl
    );

    if (!valid) {
      setError(
        "Esse link não pertence à plataforma selecionada."
      );
      setConfirmed(false);
      return;
    }

    updateExperience({
      music: {
        provider: selectedProvider,
        url: cleanUrl,
      },
    });

    setUrl(cleanUrl);
    setError("");
    setConfirmed(true);
  }

  function removeMusic() {
    setSelectedProvider("none");
    setUrl("");
    setError("");

    updateExperience({
      music: {
        provider: "none",
        url: "",
      },
    });

    setConfirmed(true);
  }

  return (
    <FadeIn>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          Etapa 7
        </span>

        <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-5xl font-black text-transparent">
          Escolha a trilha sonora
        </h1>

        <p className="mt-5 max-w-2xl text-slate-300">
          Escolha uma música que tenha significado para essa
          história.
        </p>

        {/* PLATAFORMAS */}
        <div className="mt-12 grid gap-5 md:grid-cols-2">
          {musicOptions.map((option) => {
            const selected =
              selectedProvider === option.id;

            return (
              <button
                key={option.id}
                type="button"
                onClick={() =>
                  selectProvider(option.id)
                }
                className={`
                  rounded-3xl
                  border
                  p-7
                  text-left
                  backdrop-blur-xl
                  transition-all
                  duration-300
                  ${
                    selected
                      ? "border-yellow-400 bg-yellow-400/10 shadow-[0_0_40px_rgba(250,204,21,.18)]"
                      : "border-white/10 bg-white/5 hover:border-yellow-400/60 hover:bg-white/10"
                  }
                `}
              >
                <div className="flex items-start justify-between">
                  <span className="text-4xl">
                    {option.icon}
                  </span>

                  {selected && (
                    <span className="rounded-full bg-yellow-400 px-3 py-1 text-xs font-bold text-black">
                      Selecionado
                    </span>
                  )}
                </div>

                <h2 className="mt-6 text-xl font-bold text-white">
                  {option.title}
                </h2>

                <p className="mt-2 text-sm leading-6 text-slate-400">
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>

        {/* CAMPO DA URL */}
        {selectedProvider !== "none" && (
          <div className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-7 backdrop-blur-xl">
            <div className="flex items-start gap-4">
              <div className="text-3xl">
                {
                  musicOptions.find(
                    (option) =>
                      option.id === selectedProvider
                  )?.icon
                }
              </div>

              <div>
                <h2 className="text-xl font-bold text-white">
                  Link da música
                </h2>

                <p className="mt-1 text-sm text-slate-400">
                  Cole o link da música escolhida.
                </p>
              </div>
            </div>

            <input
              type="url"
              value={url}
              onChange={(event) =>
                handleUrlChange(event.target.value)
              }
              placeholder={getPlaceholder(
                selectedProvider
              )}
              className="
                mt-6
                w-full
                rounded-2xl
                border
                border-white/10
                bg-black/20
                px-5
                py-4
                text-white
                outline-none
                placeholder:text-slate-600
                transition-all
                focus:border-yellow-400
                focus:ring-2
                focus:ring-yellow-400/20
              "
            />

            {error && (
              <div className="mt-4 rounded-2xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            )}

            {confirmed && (
              <div className="mt-4 rounded-2xl border border-green-400/20 bg-green-400/10 px-4 py-3 text-sm text-green-300">
                ✓ Música adicionada à experiência.
              </div>
            )}

            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={confirmMusic}
                className="
                  rounded-full
                  bg-yellow-400
                  px-7
                  py-3
                  font-semibold
                  text-black
                  transition-all
                  hover:scale-105
                  hover:bg-yellow-300
                "
              >
                Confirmar música
              </button>

              {confirmed && (
                <button
                  type="button"
                  onClick={removeMusic}
                  className="
                    rounded-full
                    bg-white/10
                    px-7
                    py-3
                    font-semibold
                    text-white
                    transition-colors
                    hover:bg-red-500
                  "
                >
                  Remover
                </button>
              )}
            </div>
          </div>
        )}

        {/* SEM MÚSICA */}
        {selectedProvider === "none" && (
          <div className="mt-8 rounded-3xl border border-white/10 bg-white/0.03 p-8 text-center">
            <div className="text-5xl">
              🔇
            </div>

            <h2 className="mt-5 text-2xl font-bold text-white">
              Experiência sem música
            </h2>

            <p className="mx-auto mt-3 max-w-lg text-slate-400">
              Tudo certo. A música é completamente opcional e
              você pode continuar sem adicionar uma trilha sonora.
            </p>
          </div>
        )}

        {/* AVISO */}
        <div className="mt-8 rounded-2xl border border-white/10 bg-white/0.03 p-5">
          <div className="flex gap-3">
            <span className="text-xl">
              💡
            </span>

            <div>
              <h3 className="font-semibold text-white">
                A música não será armazenada pelo MemoVerse
              </h3>

              <p className="mt-1 text-sm leading-6 text-slate-400">
                Guardaremos apenas a plataforma e o link da
                música. A integração com o serviço será feita
                posteriormente através dos recursos oficiais da
                plataforma.
              </p>
            </div>
          </div>
        </div>
      </section>
    </FadeIn>
  );
}