"use client";

import InconsistenciesPanel from "@/components/admin/InconsistenciesPanel";
import InfraStatusPanel from "@/components/admin/InfraStatusPanel";
import LifecycleAlertsPanel from "@/components/admin/LifecycleAlertsPanel";
import PaymentsByStatusPanel from "@/components/admin/PaymentsByStatusPanel";
import StatCard from "@/components/admin/StatCard";
import { useAdminDashboardData } from "@/components/admin/useAdminDashboardData";

function PageHeader() {
  return (
    <div>
      <h1 className="text-2xl font-black sm:text-3xl">Dashboard</h1>
      <p className="mt-1 text-sm text-slate-400">
        Dados lidos diretamente de lifecycle_inventory e lifecycle_cleanup (só banco local) — nada aqui é
        armazenado ou recalculado no frontend. A reconciliação com a Mercado Pago não roda automaticamente aqui;
        fica disponível como ação explícita na seção Lifecycle.
      </p>
    </div>
  );
}

export default function AdminDashboardPage() {
  const { inventory, cleanup, loading, error } = useAdminDashboardData();

  if (error) {
    return (
      <div className="flex flex-col gap-10">
        <PageHeader />
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar os dados administrativos agora. Tente recarregar a página.
        </div>
      </div>
    );
  }

  if (loading || !inventory || !cleanup) {
    return (
      <div className="flex flex-col gap-10">
        <PageHeader />
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando dados administrativos…
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-10">
      <PageHeader />

      <div className="grid grid-cols-2 gap-4 sm:gap-6 lg:grid-cols-4">
        <StatCard emoji="👤" value={inventory.users.total} label="Usuários" />
        <StatCard emoji="🌌" value={inventory.drafts.total} label="Experiências (total)" />
        <StatCard emoji="⭐" value={inventory.drafts.by_status.published.count} label="Publicadas" />
        <StatCard emoji="📝" value={inventory.drafts.by_status.draft.count} label="Drafts em andamento" />
      </div>

      <PaymentsByStatusPanel inventory={inventory} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <LifecycleAlertsPanel cleanup={cleanup} />
        <InconsistenciesPanel inventory={inventory} />
      </div>

      <InfraStatusPanel inventory={inventory} />
    </div>
  );
}
