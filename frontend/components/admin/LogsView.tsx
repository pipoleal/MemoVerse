"use client";

import { useState } from "react";

import AdminPagination from "@/components/admin/AdminPagination";
import { useAdminPaginatedList } from "@/components/admin/useAdminPaginatedList";

// Forma de cada linha de GET /api/ops/9b4/webhook-events/ (ver
// apps.ops.views.WebhookEventListView) — registro de idempotência dos
// webhooks da Mercado Pago. Nunca inclui `payload` (corpo bruto da
// notificação).
type AdminWebhookEventRow = {
  id: string;
  notification_id: string;
  topic: string;
  resource_id: string;
  status: "received" | "processed" | "failed";
  error_detail: string;
  created_at: string;
};

const STATUS_LABELS: Record<AdminWebhookEventRow["status"], string> = {
  received: "Recebido",
  processed: "Processado",
  failed: "Falhou",
};

const LIMIT = 25;

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export default function LogsView() {
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, loading, error } = useAdminPaginatedList<AdminWebhookEventRow>(
    "/ops/9b4/webhook-events/",
    LIMIT,
    offset,
    statusFilter || undefined
  );

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black sm:text-3xl">Logs</h1>
          <p className="mt-1 text-sm text-slate-400">
            Webhooks recebidos da Mercado Pago — registro de idempotência, nunca o corpo bruto da notificação.
          </p>
        </div>

        <select
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setOffset(0);
          }}
          className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 backdrop-blur-xl"
        >
          <option value="">Todos os status</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value} className="bg-slate-900">
              {label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar os logs agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando logs…
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold sm:px-8">Tópico</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Recurso</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Status</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Erro</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Recebido em</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.results.map((event) => (
                  <tr key={event.id} className="transition hover:bg-white/5">
                    <td className="px-6 py-4 text-slate-300 sm:px-8">{event.topic}</td>
                    <td className="px-6 py-4 font-mono text-xs text-slate-500 sm:px-8">{event.resource_id}</td>
                    <td className="px-6 py-4 sm:px-8">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                          event.status === "failed"
                            ? "bg-red-400/15 text-red-300"
                            : "bg-white/10 text-slate-300"
                        }`}
                      >
                        {STATUS_LABELS[event.status]}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{event.error_detail || "—"}</td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{formatDateTime(event.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <AdminPagination count={data.count} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
        </div>
      )}
    </div>
  );
}
