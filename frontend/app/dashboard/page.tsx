import ExperienceList from "@/components/dashboard/ExperienceList";
import GalaxyHero from "@/components/dashboard/GalaxyHero";
import Greeting from "@/components/dashboard/Greeting";
import QuickActions from "@/components/dashboard/QuickActions";
import Stats from "@/components/dashboard/Stats";
import Universe from "@/components/universe/Universe";

export default function DashboardPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950">
      <Universe />

      <section className="relative z-10 mx-auto flex max-w-7xl flex-col gap-12 px-8 py-24">
        <GalaxyHero />

        <Greeting />

        <QuickActions />

        <Stats />

        <section>
          <h2 className="mb-8 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-3xl font-bold text-transparent">
            Últimas experiências
          </h2>

          <ExperienceList />
        </section>
      </section>
    </main>
  );
}