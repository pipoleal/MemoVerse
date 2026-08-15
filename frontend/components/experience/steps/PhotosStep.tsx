"use client";

import Image from "next/image";
import { useRef, type ChangeEvent } from "react";

import FadeIn from "../../animations/FadeIn";
import { useExperience, type MediaEntry } from "../context/ExperienceContext";
import { uploadMediaFile, validateFileForUpload } from "@/lib/mediaUpload";

const MAX_PHOTOS = 10;

export default function PhotosStep() {
  const { photoEntries, setPhotoEntries, ensureDraftId } = useExperience();

  // AbortControllers are not serializable, so they live outside React state,
  // keyed by the same stable entry id used in photoEntries. Deliberately
  // NOT aborted on component unmount: photoEntries lives in context (not
  // local state), and this step remounts every time the user navigates back
  // to it, so an in-flight upload must keep running (and keep updating
  // context state) across step changes — only an explicit "Remover" click
  // aborts a specific upload.
  const abortControllers = useRef<Map<string, AbortController>>(new Map());

  async function runUpload(entryId: string, file: File) {
    const draftId = await ensureDraftId();

    if (!draftId) {
      // Anonymous visitor: no draft can exist yet (POST /experiences/drafts/
      // requires auth), so the file stays local-preview-only. Nothing to
      // retry here until the user has an account.
      return;
    }

    const controller = new AbortController();
    abortControllers.current.set(entryId, controller);

    setPhotoEntries((current) =>
      current.map((entry) => (entry.id === entryId ? { ...entry, status: "uploading", progress: 0, errorMessage: undefined } : entry))
    );

    try {
      const mediaId = await uploadMediaFile(
        draftId,
        "photo",
        file,
        (progress) => {
          setPhotoEntries((current) =>
            current.map((entry) => (entry.id === entryId ? { ...entry, progress } : entry))
          );
        },
        controller.signal
      );

      setPhotoEntries((current) =>
        current.map((entry) => (entry.id === entryId ? { ...entry, status: "uploaded", progress: 100, mediaId } : entry))
      );
    } catch (error) {
      if (controller.signal.aborted) return;

      setPhotoEntries((current) =>
        current.map((entry) =>
          entry.id === entryId
            ? { ...entry, status: "error", errorMessage: error instanceof Error ? error.message : "Falha ao enviar." }
            : entry
        )
      );
    } finally {
      abortControllers.current.delete(entryId);
    }
  }

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;

    if (!files) {
      return;
    }

    const availableSlots = MAX_PHOTOS - photoEntries.length;

    if (availableSlots <= 0) {
      event.target.value = "";
      return;
    }

    const filesToAdd = Array.from(files).slice(0, availableSlots);

    const newEntries: MediaEntry[] = filesToAdd.map((file) => {
      const validationError = validateFileForUpload("photo", file);

      return {
        id: crypto.randomUUID(),
        file,
        previewUrl: URL.createObjectURL(file),
        status: validationError ? "error" : "local",
        progress: 0,
        errorMessage: validationError ?? undefined,
      };
    });

    setPhotoEntries((current) => [...current, ...newEntries]);

    newEntries
      .filter((entry) => entry.status === "local")
      .forEach((entry) => {
        void runUpload(entry.id, entry.file);
      });

    event.target.value = "";
  }

  function retryUpload(entry: MediaEntry) {
    void runUpload(entry.id, entry.file);
  }

  function removePhoto(entryId: string) {
    abortControllers.current.get(entryId)?.abort();
    abortControllers.current.delete(entryId);

    setPhotoEntries((current) => {
      const target = current.find((entry) => entry.id === entryId);
      if (target?.previewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return current.filter((entry) => entry.id !== entryId);
    });
  }

  const photosCount = photoEntries.length;
  const limitReached = photosCount >= MAX_PHOTOS;

  return (
    <FadeIn>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          Etapa 4
        </span>

        <div className="mt-3 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="bg-linear-to-r from-white to-yellow-300 bg-clip-text text-5xl font-black text-transparent">
              Suas memórias em fotos
            </h1>

            <p className="mt-5 max-w-2xl text-slate-300">
              Adicione as fotos que fazem parte dessa história.
            </p>
          </div>

          <div
            className={`
              shrink-0 rounded-full border px-4 py-2 text-sm font-semibold
              ${
                limitReached
                  ? "border-yellow-400/40 bg-yellow-400/10 text-yellow-300"
                  : "border-white/10 bg-white/5 text-slate-300"
              }
            `}
          >
            {limitReached ? "✓ " : ""}
            {photosCount} / {MAX_PHOTOS} fotos
          </div>
        </div>

        <div className="mt-12">
          <label
            htmlFor="experience-photos"
            className={`
              flex
              min-h-64
              flex-col
              items-center
              justify-center
              rounded-3xl
              border
              border-dashed
              p-10
              text-center
              backdrop-blur-xl
              transition-all
              duration-300
              ${
                limitReached
                  ? "cursor-not-allowed border-white/10 bg-white/2 opacity-60"
                  : "cursor-pointer border-white/20 bg-white/5 hover:border-yellow-400 hover:bg-white/10"
              }
            `}
          >
            <span className="text-6xl">
              {limitReached ? "✓" : "📸"}
            </span>

            <h2 className="mt-6 text-2xl font-bold text-white">
              {limitReached
                ? "Limite de fotos atingido"
                : "Adicione suas memórias"}
            </h2>

            <p className="mt-3 max-w-md text-slate-400">
              {limitReached
                ? "Você já adicionou as 10 fotos permitidas nesta experiência."
                : "Escolha até 10 fotos para fazer parte dessa história."}
            </p>

            {!limitReached && (
              <span className="mt-6 rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105">
                Escolher fotos
              </span>
            )}

            <input
              id="experience-photos"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              disabled={limitReached}
              className="hidden"
              onChange={handleFiles}
            />
          </label>
        </div>

        {photoEntries.length > 0 && (
          <div className="mt-10">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-xl font-bold text-white">
                Memórias adicionadas
              </h2>

              <span className="text-sm text-slate-400">
                {photosCount} de {MAX_PHOTOS}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
              {photoEntries.map((entry, index) => (
                <div
                  key={entry.id}
                  className="group relative aspect-square overflow-hidden rounded-2xl border border-white/10 bg-white/5"
                >
                  <Image
                    src={entry.previewUrl}
                    alt={`Memória ${index + 1}`}
                    fill
                    unoptimized
                    className="object-cover transition-transform duration-500 group-hover:scale-105"
                  />

                  {entry.status === "uploading" && (
                    <div className="absolute inset-x-0 top-0 h-1.5 bg-black/40">
                      <div
                        className="h-full bg-yellow-400 transition-all duration-200"
                        style={{ width: `${entry.progress}%` }}
                      />
                    </div>
                  )}

                  <div className="absolute left-2 top-2">
                    {entry.status === "uploading" && (
                      <span className="rounded-full bg-black/70 px-2 py-1 text-[10px] font-semibold text-yellow-300">
                        Enviando {entry.progress}%
                      </span>
                    )}
                    {entry.status === "uploaded" && (
                      <span className="rounded-full bg-green-500/80 px-2 py-1 text-[10px] font-semibold text-black">
                        ✓ Salva
                      </span>
                    )}
                    {entry.status === "error" && (
                      <span className="rounded-full bg-red-500/80 px-2 py-1 text-[10px] font-semibold text-white">
                        Falhou
                      </span>
                    )}
                    {entry.status === "local" && (
                      <span className="rounded-full bg-black/70 px-2 py-1 text-[10px] font-semibold text-slate-300">
                        Só no preview
                      </span>
                    )}
                  </div>

                  <div className="absolute inset-x-0 bottom-0 flex flex-col gap-2 bg-linear-to-t from-black/80 via-black/20 to-transparent p-3 pt-10">
                    {entry.status === "error" && (
                      <p className="text-[11px] text-red-300">{entry.errorMessage}</p>
                    )}

                    <div className="flex items-end justify-between">
                      <span className="text-xs font-medium text-white">
                        Foto {index + 1}
                      </span>

                      <div className="flex gap-2">
                        {entry.status === "error" && (
                          <button
                            type="button"
                            onClick={() => retryUpload(entry)}
                            className="rounded-full bg-yellow-400 px-3 py-2 text-xs font-semibold text-black transition-colors hover:bg-yellow-300"
                          >
                            Tentar de novo
                          </button>
                        )}

                        <button
                          type="button"
                          onClick={() => removePhoto(entry.id)}
                          className="
                            rounded-full
                            bg-black/70
                            px-3
                            py-2
                            text-xs
                            font-semibold
                            text-white
                            transition-colors
                            hover:bg-red-500
                          "
                        >
                          Remover
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </FadeIn>
  );
}
