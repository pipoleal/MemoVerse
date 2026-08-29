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
// pagamentos/logs) — só troca o endpoint, o filtro de status e o campo de
// busca. Todos os parâmetros são primitivos na assinatura (nunca um
// objeto) de propósito: mantém o array de dependências do useEffect
// exato, sem precisar de JSON.stringify nem de um eslint-disable para
// react-hooks/exhaustive-deps. searchParamName é o nome do query param no
// backend (ex.: "email" em /users/, "owner_email" em /experiences/ e
// /payments/) — sempre um literal fixo no call site, nunca variável.
// reloadToken: incrementar este número força um novo fetch com os mesmos
// filtros — usado depois de uma ação de escrita (excluir usuário,
// cancelar pagamento) para recarregar a lista sem duplicar a lógica de
// fetch num "refetch()" separado.
export function useAdminPaginatedList<T>(
  endpoint: string,
  limit: number,
  offset: number,
  status?: string,
  searchParamName?: string,
  searchValue?: string,
  reloadToken = 0
): PaginatedAdminListState<T> {
  const [data, setData] = useState<PaginatedAdminReport<T> | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const params: Record<string, string> = { limit: String(limit), offset: String(offset) };
    if (status) params.status = status;
    if (searchParamName && searchValue) params[searchParamName] = searchValue;

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
  }, [endpoint, limit, offset, status, searchParamName, searchValue, reloadToken]);

  return { data, loading: data === null && !error, error };
}
