import GalaxiaVivaView from "@/components/dashboard/GalaxiaVivaView";

// Força renderização dinâmica. `export const dynamic` é ignorado
// silenciosamente em arquivos "use client" — precisa estar num Server
// Component. Ver comentário completo em app/login/page.tsx sobre o motivo
// (nonce de CSP incompatível com páginas estáticas), e app/dashboard/galaxia/page.tsx
// pelo mesmo padrão já aplicado à rota irmã.
export const dynamic = "force-dynamic";

export default function GalaxiaVivaPage() {
  return <GalaxiaVivaView />;
}
