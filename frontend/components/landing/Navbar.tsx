import Image from "next/image";
import Link from "next/link";

// Barra fixa só na landing pública ("/") — nunca reutilizada em
// dashboard/checkout/experience (que já têm sua própria navegação via
// DashboardShell). Sem estado/interação própria (só âncoras e um Link), por
// isso não precisa de "use client".
export default function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-black/60 backdrop-blur-xl">
      <div className="mx-auto flex h-20 max-w-6xl items-center justify-between px-6">
        <span className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <Image src="/brand/memoverse-emblem.png" alt="" width={32} height={32} className="h-8 w-8" priority />
          MemoVerse
        </span>

        <nav className="hidden items-center gap-8 text-sm font-semibold text-slate-300 md:flex">
          <a className="transition hover:text-white" href="#como-funciona">
            Como funciona
          </a>
          <a className="transition hover:text-white" href="#temas">
            Temas
          </a>
          <a className="transition hover:text-white" href="#galaxia-viva">
            Galáxia Viva
          </a>
          <a className="transition hover:text-white" href="#planos">
            Planos
          </a>
        </nav>

        <Link
          href="/login"
          className="rounded-full border border-white/25 px-5 py-2 text-sm font-semibold text-white transition hover:bg-white hover:text-black"
        >
          Entrar
        </Link>
      </div>
    </header>
  );
}
