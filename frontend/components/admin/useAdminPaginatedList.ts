"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";

// Forma comum de todas as listagens administrativas paginadas (ver
// apps.ops.views: UserListView/ExperienceListView/PaymentListView/
// WebhookEventListView) — limit/offset simples, nunca as classes de
// paginação do DRF.
export type PaginatedAdminReport<T> = {
  generated_at: string;
  count: number;
  limit: number;
  offset: number;
  results: T[];
};

export type PaginatedAdminListState<T> = {
  data: PaginatedAdminReport<T> | null;
  loading: boolean;
  error: boolean;
};

// Genérico o bastante para as 4 listagens (usuários/experiências/
// pagamentos/logs) — só troca o endpoint e o filtro de status. limit/
// offset/status são primitivos na assinatura (não um objeto) de propósito:
// mantém o array de dependências do useEffect exato, sem precisar de
// JSON.stringify nem de um eslint-disable para react-hooks/
// exhaustive-deps.
export function useAdminPaginatedList<T>(
  endpoint: string,
  limit: number,
  offset: number,
  status?: string
): PaginatedAdminListState<T> {
  const [data, setData] = useState<PaginatedAdminReport<T> | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const params: Record<string, string> = { limit: String(limit), offset: String(offset) };
    if (status) params.status = status;

    api
      .get<PaginatedAdminReport<T>>(endpoint, { params })
      .then((response) => {
        if (cancelled) return;
        setData(response.data);
        setError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, [endpoint, limit, offset, status]);

  return { data, loading: data === null && !error, error };
}
