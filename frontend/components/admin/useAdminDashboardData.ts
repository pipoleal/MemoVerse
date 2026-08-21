"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// Tipos abaixo cobrem só os campos que o dashboard renderiza — não são uma
// cópia completa dos relatórios (ver apps.ops.views/apps.experiences.
// management.commands.lifecycle_inventory/lifecycle_cleanup, que continuam
// a única fonte de verdade sobre a forma completa de cada relatório).

type CountEntry = { count: number };

export type InventoryReport = {
  drafts: {
    total: number;
    by_status: Record<"draft" | "awaiting_payment" | "payment_failed" | "paid" | "published", CountEntry>;
  };
  payments: {
    total: number;
    by_status: Record<
      "pending" | "in_process" | "action_required" | "approved" | "rejected" | "cancelled" | "expired" | "refunded",
      CountEntry
    >;
    active_payment_with_inconsistent_draft_status: number;
  };
  media: {
    total: number;
    without_draft: number;
  };
  r2: { checked: boolean };
  users: { total: number };
};

export type CleanupCandidate = { count: number };

export type CleanupPreviewReport = {
  candidates: {
    draft_abandoned: CleanupCandidate;
    draft_payment_failed: CleanupCandidate;
    media_pending_stale: CleanupCandidate;
    media_failed_stale: CleanupCandidate;
  };
  never_removed: {
    payment_invariant_inconsistent: CleanupCandidate;
  };
};

export type AdminDashboardData = {
  inventory: InventoryReport | null;
  cleanup: CleanupPreviewReport | null;
  loading: boolean;
  error: boolean;
};

// Só 2 chamadas, cada uma um GET simples contra um endpoint já existente e
// já protegido por IsProductionAdmin no backend (ver apps.ops.urls) —
// nenhuma query de lifecycle é reimplementada aqui, só consumida.
//
// De propósito, o dashboard NUNCA chama GET /ops/9b4/payment-reconcile/:
// diferente de lifecycle-inventory e lifecycle-cleanup-preview (que só
// leem o banco local), payment-reconcile faz chamadas de rede reais à
// Mercado Pago para cada Payment ativo parado — chamar isso toda vez que
// um admin abre ou recarrega /admin bateria na Mercado Pago repetidamente
// sem necessidade nenhuma. A reconciliação detalhada fica para uma ação
// explícita numa futura seção Lifecycle, nunca automática no carregamento
// do dashboard.
//
// --check-r2 também não é passado por padrão (nem em cleanup nem em
// inventory): listar o bucket R2 inteiro a cada carregamento seria caro
// demais para uma tela que carrega toda vez que um admin entra.
//
// Sem gate de "enabled": este hook só é usado por app/admin/page.tsx, que
// só chega a montar depois que app/admin/layout.tsx já confirmou
// is_superuser (ver AdminLayout) — chamar aqui incondicionalmente no mount
// é seguro, nunca dispara antes da autorização.
export function useAdminDashboardData(): AdminDashboardData {
  const [inventory, setInventory] = useState<InventoryReport | null>(null);
  const [cleanup, setCleanup] = useState<CleanupPreviewReport | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    Promise.all([
      api.get<InventoryReport>("/ops/9b4/lifecycle-inventory/"),
      api.get<CleanupPreviewReport>("/ops/9b4/lifecycle-cleanup-preview/"),
    ])
      .then(([inventoryRes, cleanupRes]) => {
        if (cancelled) return;
        setInventory(inventoryRes.data);
        setCleanup(cleanupRes.data);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return {
    inventory,
    cleanup,
    loading: inventory === null && !error,
    error,
  };
}
