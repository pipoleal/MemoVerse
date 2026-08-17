import Universe from "@/components/universe/Universe";
import CTAButtons from "@/components/landing/CTAButtons";
import Hero from "@/components/landing/Hero";

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden">

      <Universe />

      <section className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6">

        <Hero />

        <CTAButtons />

      </section>

    </main>
  );
}