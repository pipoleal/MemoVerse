"use client";

import { type ReactNode, useState } from "react";

import Universe from "@/components/universe/Universe";
import Sidebar from "./Sidebar";

// Layout shell: fixed sidebar on desktop, drawer on mobile/tablet (state
// lives here since both the hamburger trigger and the drawer itself need
// it). Universe (the shared Canvas/Stars background also used on
// login/register) is dimmed via a wrapper opacity here only — its own
// component is untouched, so those other pages keep their current look.
export default function DashboardShell({ children }: { children: ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <div className="relative min-h-screen bg-slate-950 text-white">
      <div className="fixed inset-0 -z-10 opacity-40">
        <Universe />
      </div>

      <div className="lg:flex">
        <Sidebar mobileOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between px-6 py-5 lg:hidden">
            <span className="text-lg font-black tracking-wide">
              MEMO<span className="text-yellow-400">VERSE</span>
            </span>

            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Abrir menu"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 bg-white/5 text-lg backdrop-blur-xl"
            >
              ☰
            </button>
          </div>

          <main className="mx-auto max-w-7xl px-6 py-10 sm:px-8 lg:px-10 lg:py-16">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
