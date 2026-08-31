import FinalCta from "@/components/landing/FinalCta";
import LandingUniverse from "@/components/landing/LandingUniverse";
import GalaxyVivaSpotlight from "@/components/landing/GalaxyVivaSpotlight";
import GiftCallout from "@/components/landing/GiftCallout";
import Hero from "@/components/landing/Hero";
import HowItWorks from "@/components/landing/HowItWorks";
import IntroStatement from "@/components/landing/IntroStatement";
import Navbar from "@/components/landing/Navbar";
import OccasionsSection from "@/components/landing/OccasionsSection";
import PricingPreview from "@/components/landing/PricingPreview";
import ThemesShowcase from "@/components/landing/ThemesShowcase";
import Footer from "@/components/layout/Footer";

// Força renderização dinâmica — ver comentário em app/login/page.tsx (mesmo
// bug: nonce de CSP congelado no build em páginas estáticas, quebrando a
// hidratação). Mascarada por enquanto pelo rewrite de middleware.ts pro
// /coming-soon, mas passa a ser o que "/" de fato serve assim que o
// lançamento acontecer (ver isBeforeLaunch() em lib/launch.ts) — sem
// deploy novo nenhum no instante da virada, então o conteúdo abaixo já
// precisa estar pronto com antecedência.
export const dynamic = "force-dynamic";

export default function Home() {
  return (
    <main className="relative min-h-dvh bg-slate-950">
      {/* fixed (não absolute): fica preso à tela, não ao tamanho da página —
          continua custando só um <Canvas> do tamanho da viewport mesmo com
          a landing tendo várias telas de altura, e as estrelas ficam
          visíveis atrás de toda seção que rolar por cima (nenhuma delas tem
          fundo opaco próprio). */}
      <div className="fixed inset-0 -z-10">
        <LandingUniverse />
      </div>

      <Navbar />

      <section className="relative flex min-h-[calc(100dvh-5rem)] flex-col items-center justify-center px-6">
        <Hero />
      </section>

      <IntroStatement />
      <HowItWorks />
      <ThemesShowcase />
      <GalaxyVivaSpotlight />
      <GiftCallout />
      <OccasionsSection />
      <PricingPreview />
      <FinalCta />
      <Footer />
    </main>
  );
}
