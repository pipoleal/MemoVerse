import { api } from "./api";
import type { Experience } from "@/components/experience/types";

const PENDING_EXPERIENCE_KEY = "memoverse.pending-experience";

type PendingExperience = { experience: Experience; draftId?: string };

export type DraftPayload = {
  experience_type: string;
  theme: string;
  title: string;
  recipient_name: string;
  creator_name: string;
  event_date: string | null;
  letter: string;
  short_message: string;
  music_provider: Experience["music"]["provider"];
  music_url: string;
};

let savingDraft: Promise<string> | null = null;

function isBrowser() {
  return typeof window !== "undefined";
}

export function toPayload(experience: Experience): DraftPayload {
  return {
    experience_type: experience.type,
    theme: experience.theme,
    title: experience.title,
    recipient_name: experience.recipient,
    creator_name: experience.creator,
    event_date: experience.eventDate || null,
    letter: experience.letter,
    short_message: experience.shortMessage,
    music_provider: experience.music.provider,
    music_url: experience.music.url,
  };
}

// Exactly the shape of apps.experiences.serializers.ExperienceDraftSerializer
// (GET /experiences/drafts/<id>/) — the same endpoint DraftDetailView already
// exposed; nothing new added backend-side beyond `slug` (previous task) and
// `media[].url` (this task, see MediaSerializer).
export type DraftMediaItem = {
  id: string;
  media_type: "photo" | "video";
  original_filename: string;
  upload_status: "pending" | "uploaded" | "failed";
  sort_order: number;
  url: string | null;
};

export type DraftDetail = DraftPayload & {
  id: string;
  status: string;
  slug: string | null;
  media: DraftMediaItem[];
};

export async function fetchDraft(
  draftId: string,
  headers: Record<string, string> = {}
): Promise<DraftDetail> {
  const response = await api.get<DraftDetail>(`/experiences/drafts/${draftId}/`, { headers });
  return response.data;
}

// Inverse of toPayload — only the fields the wizard can actually resume
// (media is handled separately by the caller via photoEntries/videoEntries,
// since it maps to MediaEntry, not a plain Experience field).
export function fromPayload(payload: DraftPayload): Omit<Experience, "photos" | "videos" | "published"> {
  return {
    type: payload.experience_type,
    theme: payload.theme,
    title: payload.title,
    recipient: payload.recipient_name,
    creator: payload.creator_name,
    eventDate: payload.event_date ?? "",
    letter: payload.letter,
    shortMessage: payload.short_message,
    music: {
      provider: payload.music_provider,
      url: payload.music_url,
    },
  };
}

function isSameDraft(draft: DraftPayload & { id: string }, payload: DraftPayload) {
  return Object.entries(payload).every(([key, value]) => draft[key as keyof DraftPayload] === value);
}

export function savePendingExperience(experience: Experience) {
  if (!isBrowser()) return;
  window.sessionStorage.setItem(
    PENDING_EXPERIENCE_KEY,
    JSON.stringify({ experience } satisfies PendingExperience)
  );
}

export function getPendingExperience(): PendingExperience | null {
  if (!isBrowser()) return null;
  const stored = window.sessionStorage.getItem(PENDING_EXPERIENCE_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored) as PendingExperience;
  } catch {
    window.sessionStorage.removeItem(PENDING_EXPERIENCE_KEY);
    return null;
  }
}

export function hasPendingExperience() {
  return getPendingExperience() !== null;
}

export function clearPendingExperience() {
  if (isBrowser()) window.sessionStorage.removeItem(PENDING_EXPERIENCE_KEY);
}

export async function savePendingExperienceDraft(): Promise<string | null> {
  if (savingDraft) return savingDraft;
  const pending = getPendingExperience();
  if (!pending) return null;
  if (pending.draftId) return pending.draftId;

  savingDraft = (async () => {
    const payload = toPayload(pending.experience);
    const existing = await api.get<(DraftPayload & { id: string })[]>("/experiences/drafts/");
    const matchingDraft = existing.data.find((draft) => isSameDraft(draft, payload));
    const draft = matchingDraft
      ? matchingDraft
      : (await api.post<DraftPayload & { id: string }>("/experiences/drafts/", payload)).data;
    const latest = getPendingExperience();
    if (latest) {
      window.sessionStorage.setItem(PENDING_EXPERIENCE_KEY, JSON.stringify({ ...latest, draftId: draft.id }));
    }
    return draft.id;
  })().finally(() => {
    savingDraft = null;
  });

  return savingDraft;
}
