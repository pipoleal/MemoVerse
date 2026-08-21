"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// Exactly the shape of apps.experiences.serializers.ExperienceDraftSerializer
// (GET /api/experiences/drafts/) — no field invented beyond it.
export type DraftMedia = {
  id: string;
  media_type: "photo" | "video";
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  duration_seconds: number | null;
  sort_order: number;
  upload_status: "pending" | "uploaded" | "failed";
  uploaded_at: string | null;
  created_at: string;
  url: string | null;
};

export type DraftStatus = "draft" | "awaiting_payment" | "payment_failed" | "paid" | "published";

export type Draft = {
  id: string;
  status: DraftStatus;
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
  music_provider: string;
  music_url: string;
  media: DraftMedia[];
  created_at: string;
  updated_at: string;
};

export type DashboardData = {
  drafts: Draft[] | null;
  loading: boolean;
  error: boolean;
};

// Single fetch of GET /experiences/drafts/, called once by the Dashboard
// page and shared (via props) by JourneyStats and ExperienceSection —
// replaces the old ExperienceList.tsx + Stats.tsx pattern, where each
// component fetched the exact same endpoint independently.
export function useDashboardData(): DashboardData {
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<Draft[]>("/experiences/drafts/")
      .then((response) => {
        if (!cancelled) setDrafts(response.data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { drafts, loading: drafts === null && !error, error };
}
