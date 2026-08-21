import type { InventoryReport } from "./useAdminDashboardData";

function StatusRow({ ok, label, detail }: { ok: boolean; label: string; detail: string }) {
  return (
    <li className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3">
      <div>
        <p className="text-sm font-semibold text-slate-200">{label}</p>
        <p className="text-xs text-slate-500">{detail}</p>
      </div>
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${ok ? "bg-emerald-400" : "bg-yellow-400"}`} />
    </li>
  );
}

// Deliberadamente barato: nada aqui faz chamada de rede externa. Esta tela
// carrega toda vez que um admin acessa /admin, então tanto R2 quanto
// Mercado Pago aparecem como "não verificado neste carregamento" em vez de
// verde/vermelho — de fato não sabemos sem pagar o custo de rede a cada
// visita. A reconciliação real com a Mercado Pago
// (GET /ops/9b4/payment-reconcile/) fica para uma ação explícita numa
// futura seção Lifecycle, nunca disparada automaticamente aqui.
export default function InfraStatusPanel({ inventory }: { inventory: InventoryReport }) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
      <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">Status da infraestrutura</h2>

      <ul className="mt-6 flex flex-col gap-3">
        <StatusRow
          ok={false}
          label="Mercado Pago"
          detail="Não verificado neste carregamento — reconciliação disponível como ação explícita na seção Lifecycle."
        />
        <StatusRow
          ok={inventory.r2.checked}
          label="Cloudflare R2"
          detail={
            inventory.r2.checked
              ? "Verificado nesta consulta."
              : "Não verificado nesta consulta (evita custo de rede a cada carregamento do painel)."
          }
        />
      </ul>
    </section>
  );
}
