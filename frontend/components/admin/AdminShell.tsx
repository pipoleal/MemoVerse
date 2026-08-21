"use client";

import { type ReactNode, useState } from "react";

import { logout } from "@/lib/auth";
import type { Me } from "@/lib/adminAuth";
import AdminSidebar from "./AdminSidebar";

type AdminShellProps = {
  me: Me;
  children: ReactNode;
};

// Mesmo shell de components/dashboard/DashboardShell.tsx (sidebar fixa no
// desktop, drawer no mobile) — sem o fundo Universe/Canvas: o painel admin
// prioriza densidade de leitura de dados sobre o visual imersivo do
// produto público, mas mantém a mesma paleta (slate-950 + amarelo).
export default function AdminShell({ me, children }: AdminShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="lg:flex">
        <AdminSidebar mobileOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-4 border-b border-white/10 px-6 py-5">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Abrir menu"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/5 text-lg backdrop-blur-xl lg:hidden"
            >
              ☰
            </button>

            <span className="hidden text-sm text-slate-400 lg:block">Painel administrativo — dados reais</span>

            <div className="ml-auto flex items-center gap-3 text-sm">
              <span className="hidden text-slate-300 sm:inline">{me.email}</span>
              <button
                type="button"
                onClick={logout}
                className="rounded-full border border-white/15 bg-white/5 px-4 py-2 font-semibold text-slate-200 transition hover:border-yellow-400/40 hover:text-white"
              >
                Sair
              </button>
            </div>
          </div>

          <main className="mx-auto max-w-7xl px-6 py-10 sm:px-8 lg:px-10">{children}</main>
        </div>
      </div>
    </div>
  );
}
