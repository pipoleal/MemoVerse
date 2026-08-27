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
        {/* Minha Galáxia: /dashboard/galaxia já existe (mesma rota que a
            Sidebar usa — ver SidebarLink em Sidebar.tsx) — este card só
            navega até ela, mesmo padrão do card "Criar Experiência" abaixo.
            Não confundir com PremiumGalaxyCard ("Galáxia Viva"), uma
            funcionalidade separada que ainda não tem rota própria. */}
        <div className="flex flex-col rounded-3xl border border-white/10 bg-white/5 p-8 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 hover:border-white/20">
          <span className="text-4xl">🌌</span>

          <h3 className="mt-6 text-2xl font-bold text-white">Minha Galáxia</h3>

          <p className="mt-3 flex-1 text-slate-400">
            Todas as experiências que você criou e eternizou.
          </p>

          <Button
            variant="secondary"
            className="mt-6 w-full py-3 text-sm"
            onClick={() => router.push("/dashboard/galaxia")}
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
