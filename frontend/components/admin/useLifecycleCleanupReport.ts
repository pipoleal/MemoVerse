"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// Forma completa de GET /api/ops/9b4/lifecycle-cleanup-preview/ (ver
// apps.experiences.management.commands.lifecycle_cleanup.Command.build_report)
// — diferente de useAdminDashboardData.ts (que só tipa os poucos campos que
// o resumo do dashboard usa), este hook alimenta a página /admin/lifecycle,
// que mostra o relatório inteiro. Nenhum dos dois duplica a query: ambos só
// consomem o JSON que o backend já monta a partir do mesmo Command.
export type CleanupCandidateGroup = {
  count: number;
  sample_ids: string[];
  reason: string;
  [key: string]: unknown;
};

export type CleanupNeverRemovedGroup = {
  count: number;
  reason: string;
  [key: string]: unknown;
};

export type FullCleanupPreviewReport = {
  generated_at: string;
  mode: string;
  policy: {
    draft_abandoned_days: number;
    draft_anonymous_unclaimed_hours: number;
    payment_failed_days: number;
    media_pending_minutes: number;
    media_failed_days: number;
    r2_orphan_grace_days: number;
  };
  candidates: {
    draft_abandoned: CleanupCandidateGroup;
    draft_anonymous_unclaimed: CleanupCandidateGroup;
    draft_payment_failed: CleanupCandidateGroup;
    media_pending_stale: CleanupCandidateGroup;
    media_failed_stale: CleanupCandidateGroup;
    r2_orphans_past_grace: { checked: boolean; reason?: string; count?: number };
  };
  never_removed: {
    draft_paid_unpublished: CleanupNeverRemovedGroup;
    draft_published_expired: CleanupNeverRemovedGroup;
    payment_financial_terminal: CleanupNeverRemovedGroup;
    payment_invariant_inconsistent: CleanupNeverRemovedGroup;
    webhook_events: CleanupNeverRemovedGroup;
    r2_missing_but_referenced: { checked: boolean; reason?: string; count?: number };
  };
};

export type LifecycleReportState = {
  report: FullCleanupPreviewReport | null;
  loading: boolean;
  error: boolean;
};

// Só leitura do banco local (nenhuma chamada de rede externa) — seguro para
// carregar automaticamente ao entrar em /admin/lifecycle, mesmo racional já
// usado por useAdminDashboardData.ts para este mesmo endpoint.
export function useLifecycleCleanupReport(): LifecycleReportState {
  const [report, setReport] = useState<FullCleanupPreviewReport | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<FullCleanupPreviewReport>("/ops/9b4/lifecycle-cleanup-preview/")
      .then((response) => {
        if (cancelled) return;
        setReport(response.data);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { report, loading: report === null && !error, error };
}
