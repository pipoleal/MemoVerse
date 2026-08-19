"use client";

import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";
import PremiumGalaxyCard from "./PremiumGalaxyCard";

export default function HeroActions() {
  const router = useRouter();

  return (
    <FadeIn delay={0.2}>
      <div className="grid gap-6 md:grid-cols-3">
        {/* Minha Galáxia: no route exists yet — prepared visually, never a
            fake navigation. Same "Em breve" contract as the Sidebar item. */}
        <div
          className="flex flex-col rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl"
          title="Em breve"
        >
          <div className="flex items-center justify-between">
            <span className="text-4xl">🌌</span>
            <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-bold tracking-wide text-slate-300">
              EM BREVE
            </span>
          </div>

          <h3 className="mt-6 text-2xl font-bold text-white">Minha Galáxia</h3>

          <p className="mt-3 flex-1 text-slate-400">
            Todas as experiências que você criou e eternizou.
          </p>

          <Button
            variant="secondary"
            disabled
            className="mt-6 w-full cursor-not-allowed py-3 text-sm opacity-40 hover:scale-100 hover:-translate-y-0 hover:bg-transparent hover:text-white"
          >
            Explorar galáxia
          </Button>
        </div>

        <div className="flex flex-col rounded-3xl border border-yellow-400/30 bg-yellow-400/5 p-8 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-yellow-400/60 hover:shadow-[0_0_50px_rgba(250,204,21,.2)]">
          <span className="text-4xl">✨</span>

          <h3 className="mt-6 text-2xl font-bold text-white">Criar Experiência</h3>

          <p className="mt-3 flex-1 text-slate-300">
            Crie uma nova experiência especial para alguém.
          </p>

          <Button className="mt-6 w-full py-3 text-sm" onClick={() => router.push("/experience/new")}>
            Criar agora
          </Button>
        </div>

        <PremiumGalaxyCard />
      </div>
    </FadeIn>
  );
}
