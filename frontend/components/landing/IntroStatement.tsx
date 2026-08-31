"use client";

import { useRouter } from "next/navigation";

import { cormorant } from "@/lib/fonts";
import FadeIn from "../animations/FadeIn";

// Substitui o antigo CTAButtons.tsx (par de botões colado embaixo do
// Hero) — no design do PDF do lançamento isso virou sua própria seção,
// com uma frase de efeito e um segundo link para a Galáxia Viva.
export default function IntroStatement() {
  const router = useRouter();

  return (
    <section className="px-6 py-24 text-center sm:py-32">
      <FadeIn>
        <h1 className={`${cormorant.className} mx-auto max-w-3xl text-4xl italic leading-tight text-white sm:text-5xl md:text-6xl`}>
          Toda data especial merece o próprio universo.
        </h1>
        <p className="mx-auto mt-6 max-w-xl text-slate-400">
          Escolha uma data, adicione fotos/vídeos, uma mensagem e uma trilha sonora — e transforme isso numa
          experiência que se pode revisitar, compartilhar e ver crescer.
        </p>

        <div className="mt-10 flex flex-col items-center gap-4">
          <button
            type="button"
            onClick={() => router.push("/experience/new")}
            className="rounded-full border border-yellow-400/60 px-8 py-4 text-sm font-bold uppercase tracking-[0.15em] text-yellow-300 transition-all duration-300 hover:-translate-y-1 hover:bg-yellow-400 hover:text-black hover:shadow-[0_0_40px_rgba(250,204,21,.35)]"
          >
            Criar experiência
          </button>
          <a href="#galaxia-viva" className="text-sm font-semibold text-slate-300 underline underline-offset-4 transition hover:text-white">
            Ver Galáxia Viva
          </a>
        </div>
      </FadeIn>
    </section>
  );
}
