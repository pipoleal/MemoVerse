// Estado transitório enquanto o guard de /admin ainda não sabe se o
// usuário é admin (aguardando getAccessToken()/GET /auth/me/). Nunca
// renderiza nenhum dado do painel neste estado.
export default function AdminChecking() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
      <div className="flex flex-col items-center gap-4">
        <span className="h-10 w-10 animate-spin rounded-full border-2 border-white/20 border-t-yellow-400" />
        <p className="text-sm text-slate-400">Verificando permissões…</p>
      </div>
    </div>
  );
}
