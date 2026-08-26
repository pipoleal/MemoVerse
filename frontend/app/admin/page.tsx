import AdminDashboardView from "@/components/admin/AdminDashboardView";

// Força renderização dinâmica. `export const dynamic` é ignorado
// silenciosamente em arquivos "use client" (confirmado: a versão anterior
// deste page.tsx, que era client component, continuava sendo prerenderizada
// estaticamente mesmo com esse export presente) — precisa estar num Server
// Component. Ver comentário completo em app/login/page.tsx sobre o motivo
// (nonce de CSP incompatível com páginas estáticas).
export const dynamic = "force-dynamic";

export default function AdminDashboardPage() {
  return <AdminDashboardView />;
}
