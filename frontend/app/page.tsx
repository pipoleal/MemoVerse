import Universe from "@/components/universe/Universe";
import CTAButtons from "@/components/landing/CTAButtons";
import Hero from "@/components/landing/Hero";

// Força renderização dinâmica — ver comentário em app/login/page.tsx (mesmo
// bug: nonce de CSP congelado no build em páginas estáticas, quebrando a
// hidratação). Mascarada por enquanto pelo rewrite de middleware.ts pro
// /coming-soon, mas passa a ser o que "/" de fato serve assim que o
// lançamento acontecer — precisa estar corrigida com antecedência.
export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <main className="relative min-h-dvh overflow-hidden">

      <Universe />

      <section className="relative z-10 flex min-h-dvh flex-col items-center justify-center px-6">

        <Hero />

        <CTAButtons />

      </section>

    </main>
  );
}