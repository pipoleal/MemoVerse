"use client";

import Image from "next/image";
import { useRef, useState, type ChangeEvent, type FocusEvent } from "react";

import FadeIn from "../../animations/FadeIn";
import { useExperience, type MediaEntry } from "../context/ExperienceContext";
import { type ExperienceTypeId } from "../informationStepConfig";
import { deleteMediaFile, uploadMediaFile, updateMediaCaption, validateFileForUpload, MAX_CAPTION_LENGTH } from "@/lib/mediaUpload";

const MAX_PHOTOS = 10;

// Sugestões de legenda por tipo de experiência — só o placeholder do
// textarea muda; o valor salvo da caption continua exatamente o que o
// usuário digita (handleCaptionChange/handleCaptionBlur, abaixo, não leem
// isto). Rotaciona por índice da foto (index % length) pra não repetir a
// mesma frase em todas as fotos da mesma experiência.
const CAPTION_SUGGESTIONS: Record<ExperienceTypeId, string[]> = {
  birthday: [
    "Mais um ano, mais motivos pra celebrar você 🎂",
    "Feliz por poder comemorar você hoje 🥳",
    "Que seu novo ano seja tão especial quanto você ✨",
  ],
  dating: [
    "O começo da nossa história ❤️",
    "Foi aqui que tudo começou",
    "Ainda lembro exatamente como me senti",
  ],
  marriage: [
    "O começo do resto das nossas vidas 💍",
    "Um momento que vamos guardar para sempre",
    "O dia em que escolhemos nosso futuro juntos ❤️",
  ],
  monthiversary: [
    "Mais um mês, mais uma memória nossa 🤍",
    "Pequenos momentos que viram grandes lembranças",
    "Mais tempo juntos, mais histórias pra contar",
  ],
  tribute: [
    "Uma lembrança que guardo com muito carinho",
    "Uma pessoa que merece ser lembrada para sempre ❤️",
    "Uma memória que sempre vai ter um lugar especial",
  ],
  custom: [
    "Um momento que merece ser lembrado ✨",
    "Essa foto guarda um pedacinho da nossa história",
    "Uma memória especial para guardar",
  ],
};

const DEFAULT_CAPTION_PLACEHOLDER = "✏️ Adicione uma mensagem para esta foto...";

// Tipo desconhecido/vazio (rascunho ainda sem tipo escolhido, ou valor
// legado) cai no placeholder genérico de sempre — nunca quebra, mesmo
// fallback pattern de getInformationStepConfig em informationStepConfig.ts.
function getCaptionPlaceholder(type: string | undefined, index: number): string {
  const suggestions = type && type in CAPTION_SUGGESTIONS ? CAPTION_SUGGESTIONS[type as ExperienceTypeId] : undefined;
  return suggestions ? suggestions[index % suggestions.length] : DEFAULT_CAPTION_PLACEHOLDER;
}

export default function PhotosStep() {
  const { photoEntries, setPhotoEntries, ensureDraftId, experience } = useExperience();

  // AbortControllers are not serializable, so they live outside React state,
  // keyed by the same stable entry id used in photoEntries. Deliberately
  // NOT aborted on component unmount: photoEntries lives in context (not
  // local state), and this step remounts every time the user navigates back
  // to it, so an in-flight upload must keep running (and keep updating
  // context state) across step changes — only an explicit "Remover" click
  // aborts a specific upload.
  const abortControllers = useRef<Map<string, AbortController>>(new Map());

  // Entries currently being deleted on the backend (disables their button
  // and shows "Removendo..."), and the last removal error per entry, if
  // any. Local to this component — never mixed into MediaEntry/context,
  // since these are transient UI states of the removal action itself.
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [removeErrors, setRemoveErrors] = useState<Record<string, string>>({});

  // Fase 2.2: mesmo padrão de removeErrors acima — erro de salvar a
  // legenda é transitório e só desta ação, nunca misturado em MediaEntry.
  const [captionErrors, setCaptionErrors] = useState<Record<string, string>>({});

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

    // Iterate filesToAdd (not newEntries) to keep `file` narrowed to the
    // concrete File type — entry.file is optional on MediaEntry in general
    // (server-loaded entries have none), but these entries were just built
    // from filesToAdd above, so the 1:1 index correspondence is exact.
    filesToAdd.forEach((file, index) => {
      if (newEntries[index].status !== "local") return;
      void runUpload(newEntries[index].id, file);
    });

    event.target.value = "";
  }

  function retryUpload(entry: MediaEntry) {
    // entry.file is only absent for server-loaded entries, which are never
    // status:"error" (the only status that renders the retry button) — the
    // guard is for TypeScript, not a real runtime case.
    if (!entry.file) return;
    void runUpload(entry.id, entry.file);
  }

  function discardEntryLocally(entryId: string) {
    setPhotoEntries((current) => {
      const target = current.find((entry) => entry.id === entryId);
      if (target?.previewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(target.previewUrl);
      }
      return current.filter((entry) => entry.id !== entryId);
    });
  }

  async function removePhoto(entryId: string) {
    const entry = photoEntries.find((item) => item.id === entryId);
    if (!entry) return;

    setRemoveErrors((current) => {
      if (!(entryId in current)) return current;
      const next = { ...current };
      delete next[entryId];
      return next;
    });

    if (!entry.mediaId) {
      // Never persisted on the backend (still local/uploading/error) —
      // nothing to delete server-side, same as before.
      abortControllers.current.get(entryId)?.abort();
      abortControllers.current.delete(entryId);
      discardEntryLocally(entryId);
      return;
    }

    const draftId = await ensureDraftId();
    if (!draftId) return;

    setDeletingIds((current) => new Set(current).add(entryId));

    try {
      await deleteMediaFile(draftId, entry.mediaId);
    } catch (error) {
      setDeletingIds((current) => {
        const next = new Set(current);
        next.delete(entryId);
        return next;
      });
      setRemoveErrors((current) => ({
        ...current,
        [entryId]: error instanceof Error ? error.message : "Não foi possível remover.",
      }));
      return;
    }

    // Fase 2.2: a legenda mora só no registro de Media, que acabou de ser
    // apagado no backend acima — nada extra a limpar aqui, discardEntryLocally
    // já remove a entrada (e a legenda com ela) do estado local também.
    discardEntryLocally(entryId);
    setDeletingIds((current) => {
      const next = new Set(current);
      next.delete(entryId);
      return next;
    });
  }

  // Fase 2.2: só atualiza o estado local a cada tecla (nunca faz PATCH
  // aqui) — quem persiste é handleCaptionBlur, abaixo.
  function handleCaptionChange(entryId: string, value: string) {
    setPhotoEntries((current) =>
      current.map((entry) => (entry.id === entryId ? { ...entry, caption: value } : entry))
    );
  }

  async function handleCaptionBlur(entry: MediaEntry, event: FocusEvent<HTMLTextAreaElement>) {
    if (!entry.mediaId) return;

    setCaptionErrors((current) => {
      if (!(entry.id in current)) return current;
      const next = { ...current };
      delete next[entry.id];
      return next;
    });

    const draftId = await ensureDraftId();
    if (!draftId) return;

    try {
      await updateMediaCaption(draftId, entry.mediaId, event.target.value);
    } catch (error) {
      setCaptionErrors((current) => ({
        ...current,
        [entry.id]: error instanceof Error ? error.message : "Não foi possível salvar a mensagem.",
      }));
    }
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
                <div key={entry.id} className="flex flex-col gap-2">
                  <div
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
                      {removeErrors[entry.id] && (
                        <p className="text-[11px] text-red-300" aria-live="polite">
                          {removeErrors[entry.id]}
                        </p>
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
                            disabled={deletingIds.has(entry.id)}
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
                              disabled:cursor-not-allowed
                              disabled:opacity-60
                              disabled:hover:bg-black/70
                            "
                          >
                            {deletingIds.has(entry.id) ? "Removendo…" : "Remover"}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Fase 2.2: irmão do quadrado acima, nunca sobreposto à
                      imagem nem ao botão Remover — só existe depois que a
                      foto realmente terminou de subir (tem mediaId real pra
                      anexar a legenda). */}
                  {entry.status === "uploaded" && (
                    <div className="flex flex-col gap-1">
                      <textarea
                        value={entry.caption ?? ""}
                        onChange={(event) => handleCaptionChange(entry.id, event.target.value)}
                        onBlur={(event) => void handleCaptionBlur(entry, event)}
                        placeholder={getCaptionPlaceholder(experience.type, index)}
                        maxLength={MAX_CAPTION_LENGTH}
                        rows={2}
                        className="
                          w-full
                          resize-none
                          rounded-xl
                          border
                          border-white/10
                          bg-white/5
                          px-3
                          py-2
                          text-xs
                          leading-relaxed
                          text-white
                          outline-none
                          placeholder:text-slate-500
                          transition-all
                          duration-300
                          focus:border-yellow-400
                          focus:bg-white/10
                          focus:ring-2
                          focus:ring-yellow-400/20
                        "
                      />
                      {captionErrors[entry.id] && (
                        <p className="text-[11px] text-red-300" aria-live="polite">
                          {captionErrors[entry.id]}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </FadeIn>
  );
}
