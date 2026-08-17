"use client";

import FadeIn from "../animations/FadeIn";

export default function GalaxyHero() {
  return (
    <FadeIn delay={0.1}>
      <section
        className="
          relative
          overflow-hidden
          rounded-[40px]
          border
          border-white/10
          bg-white/5
          p-14
          backdrop-blur-xl
        "
      >
        <div className="relative z-10">

          <p className="uppercase tracking-[0.35em] text-yellow-400 text-sm">
            Sua Galáxia
          </p>

          <h2 className="mt-4 text-6xl font-black bg-linear-to-r from-white via-slate-200 to-yellow-300 bg-clip-text text-transparent">
            Every memory becomes a star.
          </h2>

          <p className="mt-6 max-w-3xl text-slate-300 text-lg leading-8">
            Cada experiência criada ilumina uma nova estrela.
            Conforme sua história cresce, sua galáxia também cresce.
          </p>

        </div>

        <div
          className="
            absolute
            -right-20
            top-1/2
            h-80
            w-80
            -translate-y-1/2
            rounded-full
            bg-yellow-400/20
            blur-[120px]
          "
        />

      </section>
    </FadeIn>
  );
}