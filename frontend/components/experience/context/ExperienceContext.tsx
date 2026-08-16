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
import { toPayload } from "@/lib/pendingExperience";
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
  file: File;
  previewUrl: string;
  status: MediaUploadStatus;
  progress: number;
  mediaId?: string;
  errorMessage?: string;
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

  photoEntries: MediaEntry[];
  setPhotoEntries: Dispatch<SetStateAction<MediaEntry[]>>;

  videoEntries: MediaEntry[];
  setVideoEntries: Dispatch<SetStateAction<MediaEntry[]>>;
};

const ExperienceContext =
  createContext<ExperienceContextType | null>(null);

export function ExperienceProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [experience, setExperience] =
    useState<Experience>(initialExperience);

  const [draftId, setDraftId] = useState<string | null>(null);
  const ensureDraftPromiseRef = useRef<Promise<string | null> | null>(null);

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

  return (
    <ExperienceContext.Provider
      value={{
        experience: exposedExperience,
        updateExperience,
        draftId,
        ensureDraftId,
        photoEntries,
        setPhotoEntries,
        videoEntries,
        setVideoEntries,
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
