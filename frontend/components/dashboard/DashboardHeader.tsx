"use client";

import { useState } from "react";

import { logout } from "@/lib/auth";
import Greeting from "./Greeting";

export default function DashboardHeader() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
      <Greeting />

      <div className="relative shrink-0">
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-haspopup="true"
          aria-expanded={menuOpen}
          aria-label="Menu da conta"
          className="flex h-12 w-12 items-center justify-center rounded-full border border-white/15 bg-white/5 text-xl backdrop-blur-xl transition hover:border-yellow-400/50"
        >
          ✦
        </button>

        {menuOpen && (
          <>
            {/* Click-outside-to-close overlay, same pattern used elsewhere
                for lightweight menus in this codebase. */}
            <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} aria-hidden="true" />

            <div className="absolute right-0 z-20 mt-2 w-44 overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 py-1 shadow-2xl backdrop-blur-xl">
              <button
                type="button"
                onClick={logout}
                className="block w-full px-4 py-3 text-left text-sm text-slate-200 transition hover:bg-white/10"
              >
                Sair
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
