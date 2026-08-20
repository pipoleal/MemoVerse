"use client";

import Link from "next/link";

import Button from "@/components/ui/Button";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex min-h-screen w-full flex-col items-center justify-center gap-6 bg-slate-950 px-6 text-center text-white">
      <h1 className="text-2xl font-semibold">Algo deu errado.</h1>
      <p className="max-w-md text-sm text-white/60">
        Não conseguimos carregar esta página agora. Tente novamente em instantes.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-4">
        <Button type="button" onClick={reset}>
          Tentar novamente
        </Button>
        <Link href="/" className="text-sm text-white/60 underline transition hover:text-white">
          Voltar ao início
        </Link>
      </div>
    </main>
  );
}
