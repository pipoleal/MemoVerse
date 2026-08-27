import axios from "axios";

import { api } from "./api";
import type { Experience, MusicProvider, PhotoMemory } from "@/components/experience/types";

// Exactly the shape of apps.experiences.serializers.PublicExperienceSerializer
// (GET /api/public/experiences/<slug>/) — no field invented beyond it.
type PublicMedia = {
  id: string;
  media_type: "photo" | "video";
  url: string;
  original_filename: string;
  sort_order: number;
  // Fase 2.2: sempre string ("" quando não há legenda) — só usado para
  // media_type "photo" (ver toExperience abaixo); vídeo ainda não tem
  // legenda na UI, mas o campo já chega genericamente pra qualquer tipo de
  // mídia, sem exigir uma segunda migration quando isso mudar.
  caption: string;
};

export type PublicExperienceResponse = {
  slug: string;
  title: string;
  experience_type: string;
  theme: string;
  recipient_name: string;
  creator_name: string;
  event_date: string | null;
  letter: string;
  short_message: string;
  context_answer: string;
  music: { provider: string; url: string };
  media: PublicMedia[];
  published_at: string;
  // True only for the authenticated owner viewing their own published
  // experience — controls whether GalaxyChapter shows "Conhecer sua
  // galáxia" (see PublicExperienceView.tsx). Deliberately not part of
  // Experience/toExperience below: it describes the viewer, not the
  // experience itself.
  viewer_can_manage: boolean;
};

export async function fetchPublicExperience(slug: string): Promise<PublicExperienceResponse> {
  const response = await api.get<PublicExperienceResponse>(`/public/experiences/${slug}/`);
  return response.data;
}

export function isNotFoundError(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 404;
}

// POST /api/experiences/public/<slug>/save/ — "Criar minha Galáxia" (ver
// GalaxyChapter.tsx). Requires auth (the interceptor in lib/api.ts already
// attaches it); never sends anything beyond the slug already in the URL —
// the backend resolves the draft itself, the same way
// fetchPublicExperience above does, so this never accepts an id chosen by
// the caller.
export type GalaxySaveResponse = {
  id: string;
  slug: string;
};

export async function saveExperienceToGalaxy(slug: string): Promise<GalaxySaveResponse> {
  const response = await api.post<GalaxySaveResponse>(`/experiences/public/${slug}/save/`);
  return response.data;
}

// Explicit field-by-field mapping onto the existing Experience type — no
// second/parallel type is created. Only renamed/reshaped where the public
// API and the wizard's Experience genuinely disagree (snake_case API field
// names, media as a flat list vs. Experience's separate photos/videos
// string arrays); every value is either passed through as-is or dropped
// when Experience has no matching field (slug, published_at, media.id,
// media.original_filename — none of them are read by ExperienceViewer).
export function toExperience(data: PublicExperienceResponse): Experience {
  const sortedMedia = [...data.media].sort((a, b) => a.sort_order - b.sort_order);

  // Defensive: an item with an empty/missing url is dropped instead of
  // being handed to <Image>/<video> as a broken src.
  const urlsFor = (mediaType: PublicMedia["media_type"]) =>
    sortedMedia
      .filter((item) => item.media_type === mediaType && Boolean(item.url))
      .map((item) => item.url);

  // Fase 2.2: photos carrega {url, caption} — videos continua string[]
  // (urlsFor acima, inalterado) já que vídeo ainda não tem legenda na UI.
  const photos: PhotoMemory[] = sortedMedia
    .filter((item) => item.media_type === "photo" && Boolean(item.url))
    .map((item) => ({ url: item.url, caption: item.caption }));

  return {
    type: data.experience_type,
    theme: data.theme,
    title: data.title,
    recipient: data.recipient_name,
    creator: data.creator_name,
    // Experience.eventDate is a plain (non-nullable) string; the API can
    // return null for a draft that somehow has no event_date.
    eventDate: data.event_date ?? "",
    photos,
    videos: urlsFor("video"),
    letter: data.letter,
    shortMessage: data.short_message,
    contextAnswer: data.context_answer,
    music: {
      // The backend field has no DB-level choices constraint, but every
      // value that can reach it was written by the wizard's own MusicStep,
      // which only ever sends a valid MusicProvider — including "none",
      // which MusicPlayer already renders as silence, no special-casing
      // needed here.
      provider: data.music.provider as MusicProvider,
      url: data.music.url,
    },
    // PublicExperienceSerializer never exposes galaxy_live_music_url on
    // purpose (it's a dashboard-only field, see ExperienceDraftSerializer)
    // — this page (the public /e/[slug] experience) never plays that
    // track, so there is no value to map here.
    galaxyLiveMusicUrl: "",
    // Dead field on Experience today (never read anywhere) but required by
    // the type; true is the only value that is ever literally correct here
    // — this page only ever renders drafts the backend already confirmed
    // are published.
    published: true,
  };
}
