"use client";

import { useState } from "react";

import AdminConfirmDialog from "@/components/admin/AdminConfirmDialog";
import AdminPagination from "@/components/admin/AdminPagination";
import { useAdminPaginatedList } from "@/components/admin/useAdminPaginatedList";
import { useCancelPayment } from "@/components/admin/useCancelPayment";
import { useDebouncedValue } from "@/components/admin/useDebouncedValue";

// Forma de cada linha de GET /api/ops/9b4/payments/ (ver
// apps.ops.views.PaymentListView) — nunca last_sync_payload nem qualquer
// dado de cartão (o model nunca armazena isso; a tokenização é inteira do
// lado da Mercado Pago).
type AdminPaymentRow = {
  id: string;
  draft_id: string;
  owner_email: string;
  plan_code: string;
  amount: string;
  currency: string;
  status:
    | "pending"
    | "in_process"
    | "action_required"
    | "approved"
    | "rejected"
    | "cancelled"
    | "expired"
    | "refunded";
  attempt_number: number;
  mp_order_id: string | null;
  created_at: string;
  updated_at: string;
};

const STATUS_LABELS: Record<AdminPaymentRow["status"], string> = {
  pending: "Pendente",
  in_process: "Em processamento",
  action_required: "Aguardando ação (Pix)",
  approved: "Aprovado",
  rejected: "Recusado",
  cancelled: "Cancelado",
  expired: "Expirado",
  refunded: "Reembolsado",
};

const ACTIVE_STATUSES = new Set<AdminPaymentRow["status"]>(["pending", "in_process", "action_required"]);

const LIMIT = 25;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function formatAmount(amount: string, currency: string): string {
  const value = Number(amount);
  if (Number.isNaN(value)) return `${amount} ${currency}`;
  return value.toLocaleString("pt-BR", { style: "currency", currency });
}

export default function PaymentsView() {
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 400);
  const [reloadToken, setReloadToken] = useState(0);
  const [pendingCancel, setPendingCancel] = useState<AdminPaymentRow | null>(null);
  const { cancelPayment, loading: cancelling, error: cancelError, clearError } = useCancelPayment();

  const { data, loading, error } = useAdminPaginatedList<AdminPaymentRow>(
    "/ops/9b4/payments/",
    LIMIT,
    offset,
    statusFilter || undefined,
    "owner_email",
    debouncedSearch,
    reloadToken
  );

  async function confirmCancel() {
    if (!pendingCancel) return;
    const ok = await cancelPayment(pendingCancel.id);
    if (ok) {
      setPendingCancel(null);
      setReloadToken((token) => token + 1);
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black sm:text-3xl">Pagamentos</h1>
          <p className="mt-1 text-sm text-slate-400">
            Cancelar aqui é só local — nunca chama a Mercado Pago para interromper a cobrança do lado deles.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
            placeholder="Buscar por e-mail do cliente…"
            className="w-64 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 placeholder:text-slate-500 backdrop-blur-xl focus:border-yellow-400/40 focus:outline-none"
          />
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
      </div>

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar os pagamentos agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando pagamentos…
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold sm:px-8">Cliente</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Plano</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Valor</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Status</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Tentativa</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Atualizado em</th>
                  <th className="px-6 py-4 font-semibold sm:px-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.results.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-10 text-center text-slate-500 sm:px-8">
                      Nenhum pagamento encontrado.
                    </td>
                  </tr>
                )}
                {data.results.map((payment) => (
                  <tr key={payment.id} className="transition hover:bg-white/5">
                    <td className="px-6 py-4 text-slate-400 sm:px-8">{payment.owner_email}</td>
                    <td className="px-6 py-4 text-slate-400 sm:px-8">{payment.plan_code}</td>
                    <td className="px-6 py-4 font-semibold text-slate-200 sm:px-8">
                      {formatAmount(payment.amount, payment.currency)}
                    </td>
                    <td className="px-6 py-4 sm:px-8">
                      <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-slate-300">
                        {STATUS_LABELS[payment.status]}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">#{payment.attempt_number}</td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{formatDate(payment.updated_at)}</td>
                    <td className="px-6 py-4 text-right sm:px-8">
                      {ACTIVE_STATUSES.has(payment.status) && (
                        <button
                          type="button"
                          onClick={() => {
                            clearError();
                            setPendingCancel(payment);
                          }}
                          className="rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1.5 text-xs font-semibold text-red-300 transition hover:border-red-400/60 hover:text-red-200"
                        >
                          Cancelar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <AdminPagination count={data.count} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
        </div>
      )}

      {pendingCancel && (
        <AdminConfirmDialog
          title="Cancelar pagamento"
          description={`Marca o pagamento de ${pendingCancel.owner_email} (${formatAmount(pendingCancel.amount, pendingCancel.currency)}) como cancelado no MemoVerse. Isso NÃO cancela a cobrança do lado da Mercado Pago — se o cliente ainda tiver a página de checkout aberta, ela pode, em teoria, ainda ser paga.`}
          confirmLabel="Cancelar pagamento"
          danger
          loading={cancelling}
          errorMessage={cancelError}
          onConfirm={confirmCancel}
          onCancel={() => {
            setPendingCancel(null);
            clearError();
          }}
        />
      )}
    </div>
  );
}
