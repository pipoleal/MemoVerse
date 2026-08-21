import type { InventoryReport } from "./useAdminDashboardData";

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendente",
  in_process: "Em processamento",
  action_required: "Aguardando ação (Pix)",
  approved: "Aprovado",
  rejected: "Recusado",
  cancelled: "Cancelado",
  expired: "Expirado",
  refunded: "Reembolsado",
};

export default function PaymentsByStatusPanel({ inventory }: { inventory: InventoryReport }) {
  const entries = Object.entries(inventory.payments.by_status);

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
      <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">Pagamentos por status</h2>

      <ul className="mt-6 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {entries.map(([status, data]) => (
          <li key={status} className="flex items-baseline justify-between gap-2 border-b border-white/5 pb-2">
            <span className="text-sm text-slate-400">{STATUS_LABELS[status] ?? status}</span>
            <span className="text-lg font-bold text-white">{data.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
