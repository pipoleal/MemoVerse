import DashboardView from "@/components/dashboard/DashboardView";

// Força renderização dinâmica. `export const dynamic` é ignorado
// silenciosamente em arquivos "use client" — precisa estar num Server
// Component. Ver comentário completo em app/login/page.tsx sobre o motivo
// (nonce de CSP incompatível com páginas estáticas).
export const dynamic = "force-dynamic";

export default function DashboardPage() {
  return <DashboardView />;
}
