"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type AdminSidebarProps = {
  mobileOpen: boolean;
  onClose: () => void;
};

function SidebarLink({ href, icon, label, active }: { href: string; icon: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${
        active
          ? "bg-yellow-400/10 text-yellow-300"
          : "text-slate-300 hover:bg-white/5 hover:text-white"
      }`}
    >
      <span className="text-lg">{icon}</span>
      {label}
    </Link>
  );
}

// Mesmo padrão de components/dashboard/Sidebar.tsx (SidebarPreparedItem):
// itens sem rota ainda — preparados visualmente para as próximas etapas do
// painel administrativo (Usuários, Experiências, Pagamentos, Lifecycle,
// Logs, Configurações), nunca um link falso.
function SidebarPreparedItem({ icon, label }: { icon: string; label: string }) {
  return (
    <div
      className="flex cursor-not-allowed items-center justify-between rounded-2xl px-4 py-3 text-sm font-semibold text-slate-500"
      title="Em breve"
    >
      <span className="flex items-center gap-3">
        <span className="text-lg opacity-60">{icon}</span>
        {label}
      </span>

      <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold tracking-wide text-slate-300">
        EM BREVE
      </span>
    </div>
  );
}

export default function AdminSidebar({ mobileOpen, onClose }: AdminSidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={onClose} aria-hidden="true" />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-white/10 bg-slate-950/95 backdrop-blur-xl transition-transform duration-300 lg:static lg:z-auto lg:w-64 lg:translate-x-0 lg:bg-slate-950/60 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-6 py-6">
          <span className="text-lg font-black tracking-wide">
            MEMO<span className="text-yellow-400">VERSE</span>
            <span className="ml-2 rounded-full bg-yellow-400/15 px-2 py-0.5 text-[10px] font-bold tracking-wide text-yellow-300">
              ADMIN
            </span>
          </span>

          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar menu"
            className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:text-white lg:hidden"
          >
            ✕
          </button>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-4">
          <SidebarLink href="/admin" icon="📊" label="Dashboard" active={pathname === "/admin"} />

          <SidebarPreparedItem icon="👥" label="Usuários" />
          <SidebarPreparedItem icon="🌌" label="Experiências" />
          <SidebarPreparedItem icon="💳" label="Pagamentos" />
          <SidebarPreparedItem icon="♻️" label="Lifecycle" />
          <SidebarPreparedItem icon="📜" label="Logs" />
          <SidebarPreparedItem icon="⚙️" label="Configurações" />
        </nav>

        <div className="border-t border-white/10 px-6 py-4">
          <Link href="/dashboard" className="text-xs font-semibold text-slate-500 hover:text-slate-300">
            ← Voltar ao produto
          </Link>
        </div>
      </aside>
    </>
  );
}
