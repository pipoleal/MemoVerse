"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type SidebarProps = {
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

export default function Sidebar({ mobileOpen, onClose }: SidebarProps) {
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
          <SidebarLink href="/dashboard" icon="🏠" label="Dashboard" active={pathname === "/dashboard"} />

          <SidebarLink
            href="/dashboard/galaxia"
            icon="🌌"
            label="Minha Galáxia"
            active={pathname === "/dashboard/galaxia"}
          />

          {/* Etapa Galáxia Viva: graduou pra link real (mesmo caminho que
              "Minha Galáxia" já tinha percorrido) — /dashboard/galaxia-viva
              decide sozinha o que mostrar conforme o entitlement
              (galaxy_live_enabled), nunca uma checagem prévia aqui na
              Sidebar (ver comentário em GalaxiaVivaView.tsx). */}
          <SidebarLink
            href="/dashboard/galaxia-viva"
            icon="✨"
            label="Galáxia Viva"
            active={pathname === "/dashboard/galaxia-viva"}
          />

          <SidebarLink href="/experience/new" icon="➕" label="Criar Experiência" active={pathname === "/experience/new"} />
        </nav>
      </aside>
    </>
  );
}
