"use client";

import { useEffect, useState } from "react";
import axios from "axios";

import { api } from "@/lib/api";

// Forma de GET /api/ops/9b4/experiences/<id>/ (ver
// apps.ops.views.ExperienceDetailView) — ÚNICA rota que expõe conteúdo
// privado da experiência. Cada acesso é logado no backend com o e-mail do
// admin.
export type AdminExperienceMedia = {
  id: string;
  media_type: "photo" | "video";
  upload_status: "pending" | "uploaded" | "failed";
  caption: string;
  sort_order: number;
  url: string | null;
};

export type AdminExperienceDetail = {
  id: string;
  owner_email: string | null;
  status: string;
  slug: string | null;
  experience_type: string;
  theme: string;
  title: string;
  recipient_name: string;
  creator_name: string;
  event_date: string | null;
  letter: string;
  short_message: string;
  context_answer: string;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  expires_at: string | null;
  media: AdminExperienceMedia[];
};

export type ExperienceDetailState = {
  data: AdminExperienceDetail | null;
  loading: boolean;
  error: boolean;
  notFound: boolean;
};

export function useExperienceDetail(draftId: string): ExperienceDetailState {
  const [data, setData] = useState<AdminExperienceDetail | null>(null);
  const [error, setError] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<AdminExperienceDetail>(`/ops/9b4/experiences/${draftId}/`)
      .then((response) => {
        if (cancelled) return;
        setData(response.data);
      })
      .catch((err) => {
        if (cancelled) return;
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setNotFound(true);
        } else {
          setError(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [draftId]);

  return { data, loading: data === null && !error && !notFound, error, notFound };
}
