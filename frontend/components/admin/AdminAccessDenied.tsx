import Link from "next/link";

// Estado explícito de "autenticado, mas sem permissão" — nunca um
// redirecionamento silencioso. O requisito é que um usuário comum receba
// acesso negado visível, não que suma da tela sem explicação.
export default function AdminAccessDenied() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-slate-950 px-6 text-center text-white">
      <span className="text-5xl">🔒</span>
      <div>
        <h1 className="text-2xl font-black">Acesso restrito</h1>
        <p className="mt-2 max-w-md text-sm text-slate-400">
          Esta área é exclusiva para administradores do MemoVerse. Sua conta está autenticada, mas não tem
          permissão de administrador.
        </p>
      </div>
      <Link
        href="/dashboard"
        className="rounded-full bg-yellow-400 px-6 py-3 text-sm font-semibold text-black transition hover:scale-105"
      >
        Voltar ao MemoVerse
      </Link>
    </div>
  );
}
