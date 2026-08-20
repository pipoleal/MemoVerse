"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";

import { api } from "@/lib/api";
import { fetchDraft, fromPayload, toPayload } from "@/lib/pendingExperience";
import { getAccessToken } from "@/lib/storage";

import {
  Experience,
  initialExperience,
} from "../types";

export type MediaUploadStatus = "local" | "uploading" | "uploaded" | "error";

export interface MediaEntry {
  // Stable client-side id, independent of array position — removal and
  // concurrent uploads target entries by id, never by index.
  id: string;
  // Absent only for entries loaded from an already-uploaded server Media
  // (resuming a draft) — there is no local File object for those, and
  // nothing needs one: retryUpload() is only ever reachable from a
  // status:"error" entry, which a server-loaded entry (status:"uploaded")
  // never is.
  file?: File;
  previewUrl: string;
  status: MediaUploadStatus;
  progress: number;
  mediaId?: string;
  errorMessage?: string;
  // True for entries loaded from the server when resuming an existing
  // draft. Steps use this to hide the "Remover" action for them — there is
  // no delete endpoint for already-uploaded media (out of scope for this
  // fix), so offering a button that only removes the entry locally, while
  // the backend still counts it toward the published experience, would be
  // a silently broken action rather than a real one.
  fromServer?: boolean;
}

type ExperienceContextType = {
  experience: Experience;

  updateExperience: (
    data: Partial<Experience>
  ) => void;

  // Null until a draft exists. Only obtainable for an authenticated user —
  // the backend requires IsAuthenticated on POST /experiences/drafts/, so
  // anonymous visitors going through the wizard before signing up have no
  // draft to upload against yet.
  draftId: string | null;

  // Creates (or returns the already-created) draft for this wizard session.
  // Resolves to null when there is no access token, or if creation fails.
  ensureDraftId: () => Promise<string | null>;

  // Etapa 7: ensures a draft exists (creating it on the earliest step
  // transition that has real data to protect) and PATCHes the current
  // snapshot of every text field to it. Meant to be called from the
  // wizard's step-transition handler, fire-and-forget (not awaited) so
  // navigation never waits on it — a failure here is silently swallowed
  // (same policy as ensureDraftId) because the next step transition
  // re-sends the full snapshot anyway, self-healing any transient error
  // without needing explicit retry logic. PreviewStep keeps its own
  // separate, blocking sync (it precedes checkout) — this is deliberately
  // not shared with it, to avoid touching that already-tested path.
  syncDraftProgress: () => Promise<void>;

  photoEntries: MediaEntry[];
  setPhotoEntries: Dispatch<SetStateAction<MediaEntry[]>>;

  videoEntries: MediaEntry[];
  setVideoEntries: Dispatch<SetStateAction<MediaEntry[]>>;

  // Only meaningful when the provider was mounted with initialDraftId.
  isLoadingInitialDraft: boolean;
  initialDraftLoadError: string | null;
};

const ExperienceContext =
  createContext<ExperienceContextType | null>(null);

export function ExperienceProvider({
  children,
  initialDraftId,
}: {
  children: ReactNode;
  // When set, the provider loads this existing draft's data (text fields +
  // already-uploaded media) instead of starting from initialExperience —
  // this is what lets the Dashboard's "Continuar edição" action resume a
  // draft instead of silently starting a new one.
  initialDraftId?: string;
}) {
  const [experience, setExperience] =
    useState<Experience>(initialExperience);

  const [draftId, setDraftId] = useState<string | null>(null);
  const ensureDraftPromiseRef = useRef<Promise<string | null> | null>(null);

  const [isLoadingInitialDraft, setIsLoadingInitialDraft] = useState(Boolean(initialDraftId));
  const [initialDraftLoadError, setInitialDraftLoadError] = useState<string | null>(null);

  // ensureDraftId must always read the *latest* experience fields (title,
  // recipient, etc. filled in steps 1-3) even though the callback identity
  // below is only recreated when draftId changes — a plain closure over
  // `experience` would otherwise capture a stale, possibly-blank snapshot.
  const experienceRef = useRef(experience);
  useEffect(() => {
    experienceRef.current = experience;
  }, [experience]);

  const [photoEntries, setPhotoEntries] = useState<MediaEntry[]>([]);
  const [videoEntries, setVideoEntries] = useState<MediaEntry[]>([]);

  const updateExperience = useCallback(
    (data: Partial<Experience>) => {
      setExperience((previous) => ({
        ...previous,
        ...data,
      }));
    },
    []
  );

  // Derived, not stored: photoEntries/videoEntries are the single source of
  // truth for media. experience.photos/videos (plain preview-URL arrays,
  // consumed as-is by ExperienceViewer for the 3D preview) are recomputed
  // from them on every render instead of mirrored into state via an effect.
  const exposedExperience: Experience = {
    ...experience,
    photos: photoEntries.map((entry) => entry.previewUrl),
    videos: videoEntries.map((entry) => entry.previewUrl),
  };

  const ensureDraftId = useCallback((): Promise<string | null> => {
    if (draftId) return Promise.resolve(draftId);
    if (!getAccessToken()) return Promise.resolve(null);
    if (ensureDraftPromiseRef.current) return ensureDraftPromiseRef.current;

    const promise = (async () => {
      try {
        const payload = toPayload(experienceRef.current);
        const response = await api.post<{ id: string }>("/experiences/drafts/", payload);
        setDraftId(response.data.id);
        return response.data.id;
      } catch {
        return null;
      } finally {
        ensureDraftPromiseRef.current = null;
      }
    })();

    ensureDraftPromiseRef.current = promise;
    return promise;
  }, [draftId]);

  const syncDraftProgress = useCallback(async (): Promise<void> => {
    const id = await ensureDraftId();
    if (!id) return;

    try {
      await api.patch(`/experiences/drafts/${id}/`, toPayload(experienceRef.current));
    } catch {
      // Fire-and-forget by design (see the type comment above) — the next
      // step transition re-sends the full snapshot, so a transient failure
      // here is not fatal.
    }
  }, [ensureDraftId]);

  // Loads an existing draft's data when the provider is mounted to resume
  // one (Dashboard "Continuar edição"). `cancelled` alone (no mount-guard
  // ref) is deliberate — see PublicExperienceView.tsx for why a ref-based
  // guard combined with this pattern previously caused a permanent loading
  // state under React StrictMode's dev-only double-invoke: the ref would
  // survive the simulated remount and block the second, real effect run,
  // while `cancelled` (scoped to each run's own closure) would not, so the
  // first run's own cleanup discarded its own fetch's result. This effect
  // avoids that class of bug entirely by not using a mount-guard ref.
  useEffect(() => {
    if (!initialDraftId) return;

    let cancelled = false;

    fetchDraft(initialDraftId)
      .then((draft) => {
        if (cancelled) return;
        setDraftId(draft.id);
        setExperience((previous) => ({ ...previous, ...fromPayload(draft) }));
        setPhotoEntries(
          draft.media
            .filter((item) => item.media_type === "photo" && item.upload_status === "uploaded" && item.url)
            .map((item) => ({
              id: item.id,
              mediaId: item.id,
              previewUrl: item.url as string,
              status: "uploaded",
              progress: 100,
              fromServer: true,
            }))
        );
        setVideoEntries(
          draft.media
            .filter((item) => item.media_type === "video" && item.upload_status === "uploaded" && item.url)
            .map((item) => ({
              id: item.id,
              mediaId: item.id,
              previewUrl: item.url as string,
              status: "uploaded",
              progress: 100,
              fromServer: true,
            }))
        );
      })
      .catch(() => {
        if (cancelled) return;
        setInitialDraftLoadError(
          "Não foi possível carregar esta experiência para edição. Tente novamente em instantes."
        );
      })
      .finally(() => {
        if (cancelled) return;
        setIsLoadingInitialDraft(false);
      });

    return () => {
      cancelled = true;
    };
  }, [initialDraftId]);

  return (
    <ExperienceContext.Provider
      value={{
        experience: exposedExperience,
        updateExperience,
        draftId,
        ensureDraftId,
        syncDraftProgress,
        photoEntries,
        setPhotoEntries,
        videoEntries,
        setVideoEntries,
        isLoadingInitialDraft,
        initialDraftLoadError,
      }}
    >
      {children}
    </ExperienceContext.Provider>
  );
}

// Non-throwing variant: returns null instead of erroring when there is no
// ExperienceProvider ancestor. Exists for components that must also work
// standalone (e.g. ExperienceViewer rendered on the future public page with
// an `experience` prop, outside the wizard's Provider) — those components
// call this instead of useExperience() so mounting without a Provider is a
// valid, non-throwing state rather than a crash.
export function useOptionalExperience() {
  return useContext(ExperienceContext);
}

export function useExperience() {
  const context = useOptionalExperience();

  if (!context) {
    throw new Error(
      "useExperience deve estar dentro de ExperienceProvider."
    );
  }

  return context;
}
