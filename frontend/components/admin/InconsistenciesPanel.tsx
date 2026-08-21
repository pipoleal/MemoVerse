import type { InventoryReport } from "./useAdminDashboardData";

// O invariante investigado/corrigido na Etapa 9B.2/9B.3: Payment ativo com
// Draft fora de awaiting_payment. Read-only — a correção real passa por
// `python manage.py payment_reconcile --dry-run` (ver riscos no relatório),
// nunca por uma ação nesta tela.
export default function InconsistenciesPanel({ inventory }: { inventory: InventoryReport }) {
  const invariantCount = inventory.payments.active_payment_with_inconsistent_draft_status;
  const orphanMediaCount = inventory.media.without_draft;
  const total = invariantCount + orphanMediaCount;

  return (
    <section
      className={`rounded-3xl border p-6 backdrop-blur-xl sm:p-8 ${
        total > 0 ? "border-red-400/30 bg-red-400/5" : "border-white/10 bg-white/5"
      }`}
    >
      <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">Inconsistências</h2>

      {total === 0 ? (
        <p className="mt-6 text-sm text-slate-400">Nenhuma inconsistência estrutural encontrada.</p>
      ) : (
        <ul className="mt-6 flex flex-col gap-3">
          {invariantCount > 0 && (
            <li className="flex items-center justify-between rounded-2xl bg-red-400/10 px-4 py-3">
              <span className="text-sm text-red-200">Payment ativo com Draft fora de awaiting_payment</span>
              <span className="rounded-full bg-red-400/20 px-3 py-1 text-sm font-bold text-red-300">
                {invariantCount}
              </span>
            </li>
          )}
          {orphanMediaCount > 0 && (
            <li className="flex items-center justify-between rounded-2xl bg-red-400/10 px-4 py-3">
              <span className="text-sm text-red-200">Media sem draft (estrutural)</span>
              <span className="rounded-full bg-red-400/20 px-3 py-1 text-sm font-bold text-red-300">
                {orphanMediaCount}
              </span>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}
