"use client";

import LifecycleCleanupDetail from "@/components/admin/LifecycleCleanupDetail";
import PaymentReconcilePanel from "@/components/admin/PaymentReconcilePanel";
import { useLifecycleCleanupReport } from "@/components/admin/useLifecycleCleanupReport";

function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-black sm:text-3xl">Lifecycle</h1>
      <p className="mt-1 text-sm text-slate-400">
        Preview de retenção (só banco local, seguro para carregar automaticamente) e reconciliação de pagamentos
        com a Mercado Pago (chamada de rede real — só sob ação explícita, nunca automática).
      </p>
    </div>
  );
}

export default function LifecycleView() {
  const { report, loading, error } = useLifecycleCleanupReport();

  return (
    <div className="flex flex-col gap-10">
      <PageHeader />

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar o preview de lifecycle agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !report) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando preview de lifecycle…
        </div>
      )}

      {report && <LifecycleCleanupDetail report={report} />}

      <PaymentReconcilePanel />
    </div>
  );
}
