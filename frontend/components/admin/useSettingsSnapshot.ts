"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// Forma de GET /api/ops/9b4/settings-snapshot/ (ver
// apps.ops.views.SettingsSnapshotView) — só flags/valores operacionais
// não-secretos. NUNCA inclui SECRET_KEY, tokens/segredos da Mercado Pago,
// chaves do R2, DATABASE_URL ou RESEND_API_KEY.
export type SettingsSnapshot = {
  generated_at: string;
  debug: boolean;
  mercado_pago_environment: string;
  r2_configured: boolean;
  r2_bucket_name: string | null;
  email_backend: string;
  pending_media_expiration_minutes: number;
  memoverse_admin_email: string | null;
  allowed_hosts: string[];
};

export type SettingsSnapshotState = {
  data: SettingsSnapshot | null;
  loading: boolean;
  error: boolean;
};

export function useSettingsSnapshot(): SettingsSnapshotState {
  const [data, setData] = useState<SettingsSnapshot | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<SettingsSnapshot>("/ops/9b4/settings-snapshot/")
      .then((response) => {
        if (cancelled) return;
        setData(response.data);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { data, loading: data === null && !error, error };
}
