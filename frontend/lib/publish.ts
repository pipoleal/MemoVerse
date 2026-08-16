import axios from "axios";

import { api } from "./api";

// Exactly the shape of apps.experiences.serializers.PublishResponseSerializer.
export type PublishResponse = {
  slug: string;
  status: string;
  published_at: string;
};

// POST /api/experiences/drafts/<id>/publish/ is idempotent on the backend
// (PublicationService.publish): republishing an already-published draft
// returns the same slug, no new side effect — safe to call again on
// retry/remount, no special-casing needed on this side for that case.
export async function publishDraft(draftId: string): Promise<PublishResponse> {
  const response = await api.post<PublishResponse>(`/experiences/drafts/${draftId}/publish/`, {});
  return response.data;
}

export function extractPublishErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Não foi possível conectar ao servidor.";
  }
  return "Não foi possível publicar a experiência. Tente novamente.";
}
