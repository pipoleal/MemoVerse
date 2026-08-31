import { cormorant } from "@/lib/fonts";
import FadeIn from "../animations/FadeIn";
import UniverseEngine from "../universe/UniverseEngine";
import GalaxiaViva from "../universe/GalaxiaViva";
import type { StarData } from "../universe/types";

// Amostra só para esta vitrine — nunca dados de um usuário real (a landing
// é pública, sem sessão). Um pequeno aglomerado, não espalhado pela cena
// toda, para lembrar o agrupamento que aparece em Minha Galáxia. `color`/
// `glow` existem só para satisfazer o tipo: MemoryStars.tsx sempre desenha
// dourado, nunca lê essas duas chaves.
const SAMPLE_MEMORY_STARS: StarData[] = [
  { id: "s1", position: [-1.6, 0.4, 0], size: 0.9, color: "#ffd966", glow: "#ffd966" },
  { id: "s2", position: [-0.7, -0.5, 0.3], size: 0.7, color: "#ffd966", glow: "#ffd966" },
  { id: "s3", position: [0.1, 0.7, -0.2], size: 1.1, color: "#ffd966", glow: "#ffd966" },
  { id: "s4", position: [0.6, 0.3, 0.4], size: 0.8, color: "#ffd966", glow: "#ffd966" },
  { id: "s5", position: [0.9, -0.2, -0.3], size: 0.6, color: "#ffd966", glow: "#ffd966" },
  { id: "s6", position: [0.3, -0.8, 0.2], size: 0.75, color: "#ffd966", glow: "#ffd966" },
];

// Data fixa (nunca recalculada a partir de "hoje") — GalaxiaViva já conta
// dias/horas/minutos/segundos ao vivo a partir dela sozinho; escolhida só
// para dar um número de estrelas/dias que pareça vivido nesta vitrine.
const DEMO_SINCE = new Date("2026-07-01T00:00:00Z");

export default function GalaxyVivaSpotlight() {
  return (
    <section id="galaxia-viva" className="px-6 py-24 sm:py-32">
      <div className="mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-2">
        <FadeIn>
          <h2 className={`${cormorant.className} text-3xl italic leading-tight text-white sm:text-4xl`}>
            Memórias que você pode revisitar para sempre
          </h2>
          <p className="mt-5 text-slate-400">
            Toda experiência que você publica e toda experiência especial que alguém compartilha com você vira uma
            estrela na sua própria galáxia. Um mapa vivo das suas memórias, sempre a um clique de distância!
          </p>

          <span className="mt-10 inline-flex items-center gap-2 rounded-full border border-yellow-400/25 bg-yellow-400/10 px-4 py-1.5 text-xs font-bold uppercase tracking-[0.15em] text-yellow-300">
            ✦ Recurso exclusivo
          </span>
          <h3 className={`${cormorant.className} mt-6 text-2xl italic leading-tight text-white sm:text-3xl`}>
            Sua Galáxia Viva: tenha um contador de dias ao vivo
          </h3>
          <p className="mt-5 text-slate-400">
            Veja quanto tempo já passou desde aquele momento especial e acompanhe, em tempo real, cada novo segundo
            dessa história e observe uma nova estrela nascer diariamente.
          </p>
          <ul className="mt-7 space-y-3 text-sm text-slate-300">
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-yellow-400">✓</span>
              O tempo da sua história, em tempo real
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-yellow-400">✓</span>
              Pague uma vez e aproveite por 12 meses
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-0.5 text-yellow-400">✓</span>
              Disponível no plano Anual + Galáxia Viva
            </li>
          </ul>
        </FadeIn>

        <FadeIn delay={0.15}>
          <div className="mx-auto flex w-full max-w-md flex-col gap-5">
            {/* As duas cenas de verdade do produto (não ilustração nem
                captura estática) — os mesmos componentes usados em Minha
                Galáxia (UniverseEngine + MemoryStars) e na Galáxia Viva
                (GalaxiaViva.tsx), com dados de amostra só para esta
                vitrine pública. */}
            <div className="relative h-[220px] w-full overflow-hidden rounded-3xl border border-white/10 bg-white/5">
              <UniverseEngine memoryStars={SAMPLE_MEMORY_STARS} />
              <p className="absolute inset-x-0 bottom-0 border-t border-white/10 bg-black/40 px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-300 backdrop-blur-sm">
                Galáxia
              </p>
            </div>

            <div className="h-[260px] w-full">
              <GalaxiaViva since={DEMO_SINCE} />
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
