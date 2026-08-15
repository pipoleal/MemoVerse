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
