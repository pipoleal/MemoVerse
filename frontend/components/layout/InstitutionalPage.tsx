import type { ReactNode } from "react";
import Link from "next/link";

import Footer from "@/components/layout/Footer";

type InstitutionalPageProps = {
  eyebrow: string;
  title: string;
  updatedAt?: string;
  children: ReactNode;
};

export default function InstitutionalPage({ eyebrow, title, updatedAt, children }: InstitutionalPageProps) {
  return (
    <main className="min-h-dvh bg-slate-950 text-slate-100">
      <header className="border-b border-white/10 px-6 py-5 sm:px-8">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <Link href="/" className="text-lg font-black tracking-tight text-white transition hover:text-yellow-300">
            MemoVerse
          </Link>
          <Link href="/" className="text-sm font-medium text-slate-400 transition hover:text-white">
            Voltar ao início
          </Link>
        </div>
      </header>

      <article className="mx-auto w-full max-w-4xl px-6 py-16 sm:px-8 sm:py-24">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-yellow-400">{eyebrow}</p>
        <h1 className="mt-4 text-4xl font-black tracking-tight text-white sm:text-5xl">{title}</h1>
        {updatedAt && <p className="mt-4 text-sm text-slate-400">Última atualização: {updatedAt}</p>}
        <div className="mt-12 space-y-10 text-base leading-8 text-slate-300">{children}</div>
      </article>

      <Footer />
    </main>
  );
}
