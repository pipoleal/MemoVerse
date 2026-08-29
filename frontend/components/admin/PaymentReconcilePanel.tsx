"use client";

import type { ReconcileRow } from "./usePaymentReconcile";
import { usePaymentReconcile } from "./usePaymentReconcile";

function ReconcileRowItem({ row }: { row: ReconcileRow }) {
  if (row.query_error) {
    return (
      <li className="rounded-2xl bg-red-400/10 px-4 py-3 text-sm">
        <p className="text-red-200">
          Payment {row.payment_id.slice(0, 8)}… (draft {row.draft_id.slice(0, 8)}…)
        </p>
        <p className="mt-1 text-xs text-red-300/80">Erro na consulta: {row.query_error}</p>
      </li>
    );
  }

  return (
    <li className="rounded-2xl bg-white/5 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-xs text-slate-500">Payment {row.payment_id.slice(0, 8)}…</span>
        <span className="text-xs text-slate-400">
          local={row.local_status} → mp={row.mp_raw_status ?? "—"} mapeado={row.mapped_local_status ?? "—"}
        </span>
      </div>
      <p className="mt-1 text-slate-300">{row.recommended_action}</p>
      {row.would_transition_to && (
        <span className="mt-2 inline-block rounded-full bg-yellow-400/15 px-3 py-1 text-xs font-bold text-yellow-300">
          mudaria para: {row.would_transition_to}
        </span>
      )}
    </li>
  );
}

// Única superfície do painel que fala com a Mercado Pago. run() só é
// chamada pelo onClick abaixo — nunca por um useEffect, nunca no mount
// desta seção, nunca em um intervalo. Ver usePaymentReconcile.ts para a
// garantia completa.
export default function PaymentReconcilePanel() {
  const { report, loading, error, hasRun, run } = usePaymentReconcile();

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">
            Reconciliação com a Mercado Pago
          </h2>
          <p className="mt-1 max-w-xl text-xs text-slate-500">
            Consulta ao vivo (GET, só leitura) na Mercado Pago para pagamentos ativos parados. Nunca roda
            automaticamente — só ao clicar no botão abaixo. Nenhuma escrita é feita, no banco local ou na Mercado
            Pago.
          </p>
        </div>

        <button
          type="button"
          onClick={run}
          disabled={loading}
          className="shrink-0 rounded-full bg-yellow-400 px-6 py-3 text-sm font-semibold text-black transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:scale-100"
        >
          {loading ? "Consultando Mercado Pago…" : "Executar reconciliação"}
        </button>
      </div>

      {!hasRun && (
        <p className="mt-6 text-sm text-slate-500">Nenhuma consulta foi feita ainda nesta sessão.</p>
      )}

      {error && (
        <p className="mt-6 rounded-2xl border border-red-400/30 bg-red-400/5 p-4 text-sm text-red-200">
          Não foi possível consultar a Mercado Pago agora. Tente novamente.
        </p>
      )}

      {report && (
        <div className="mt-6 flex flex-col gap-6">
          <p className="text-xs text-slate-500">
            {report.active_payments_matching_staleness} pagamento(s) ativo(s) parado(s) há mais de{" "}
            {report.stale_minutes_used}min (limite: {report.limit_used}
            {report.candidates_capped ? ", capado" : ""}). Erros de consulta: {report.query_errors}.
          </p>

          {report.without_mp_order_id.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Sem mp_order_id (não é possível reconciliar via consulta)
              </h3>
              <ul className="mt-3 flex flex-col gap-2">
                {report.without_mp_order_id.map((row) => (
                  <ReconcileRowItem key={row.payment_id} row={row} />
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Consultados na Mercado Pago</h3>
            {report.queried.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">Nenhum pagamento elegível nesta execução.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-2">
                {report.queried.map((row) => (
                  <ReconcileRowItem key={row.payment_id} row={row} />
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
