"use client";

import { useCallback, useState } from "react";

import { api } from "@/lib/api";

// Forma de GET /api/ops/9b4/payment-reconcile/ (ver
// apps.payments.management.commands.payment_reconcile.Command.build_report).
// Nunca inclui dado de cartão/credencial — só status e IDs internos, os
// mesmos campos que o CLI já imprime para um admin real.
export type ReconcileRow = {
  payment_id: string;
  draft_id: string;
  local_status: string;
  draft_status: string;
  draft_status_consistent?: boolean;
  mp_order_id?: string | null;
  mp_raw_status?: string;
  mapped_local_status?: string;
  would_transition_to?: string | null;
  recommended_action: string;
  query_error?: string;
  updated_at?: string;
};

export type PaymentReconcileReport = {
  generated_at: string;
  mode: string;
  stale_minutes_used: number;
  limit_used: number;
  active_payments_matching_staleness: number;
  candidates_capped: boolean;
  without_mp_order_id: ReconcileRow[];
  queried: ReconcileRow[];
  query_errors: number;
};

export type PaymentReconcileState = {
  report: PaymentReconcileReport | null;
  loading: boolean;
  error: boolean;
  hasRun: boolean;
  run: () => void;
};

// IMPORTANTE: este hook nunca dispara sozinho. Diferente de
// useLifecycleCleanupReport/useAdminDashboardData (que chamam a API dentro
// de um useEffect no mount), aqui a chamada só acontece dentro de run(),
// invocada pelo clique explícito do admin no botão "Executar reconciliação"
// (ver PaymentReconcilePanel.tsx). GET /ops/9b4/payment-reconcile/ faz
// chamadas de rede reais à Mercado Pago (GET /v1/orders/{id}, só leitura) —
// carregar isso sozinho bateria na Mercado Pago toda vez que o painel
// administrativo fosse aberto ou recarregado, sem necessidade nenhuma.
export function usePaymentReconcile(): PaymentReconcileState {
  const [report, setReport] = useState<PaymentReconcileReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [hasRun, setHasRun] = useState(false);

  const run = useCallback(() => {
    setLoading(true);
    setError(false);
    setHasRun(true);

    api
      .get<PaymentReconcileReport>("/ops/9b4/payment-reconcile/")
      .then((response) => {
        setReport(response.data);
      })
      .catch(() => {
        setError(true);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return { report, loading, error, hasRun, run };
}
