"use client";

import { useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Stars } from "@react-three/drei";

import CameraRig from "@/components/universe/CameraRig";

type GalaxyChapterProps = {
  onRevive: () => void;
};

// Two local sub-states, entirely self-contained: the CTA ("Tem mais /
// Conheça sua galáxia") and the galaxy scene itself. Neither the Canvas nor
// its Three.js/WebGL context exists until the user actually clicks through —
// avoids spending a WebGL context on every playthrough that never reaches
// this chapter, and guarantees a clean mount whenever it does (the parent
// only renders this component at all while chapter === "completed", so a
// revive - which sends chapter back to "idle" - unmounts this whole
// component, tearing the Canvas down cleanly via react-three-fiber; the next
// time "completed" is reached, GalaxyChapter mounts fresh with revealed back
// at its default false).
export default function GalaxyChapter({ onRevive }: GalaxyChapterProps) {
  const [revealed, setRevealed] = useState(false);

  if (!revealed) {
    return (
      <section className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-hidden bg-black px-6 text-center text-white">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(217,180,75,0.14),transparent_55%)]" />
        <div className="relative flex flex-col items-center gap-4">
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-300">Tem mais</p>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Conheça sua galáxia</h2>
          <button
            type="button"
            onClick={() => setRevealed(true)}
            className="mt-4 cursor-pointer rounded-full bg-yellow-300 px-8 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-950 transition hover:scale-105 hover:bg-yellow-200"
          >
            Conheça sua galáxia ✨
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-black">
      <div className="absolute inset-0">
        <Canvas camera={{ position: [0, 0, 12], fov: 65 }}>
          <color attach="background" args={["#020617"]} />
          <ambientLight intensity={0.8} />
          <Stars radius={250} depth={80} count={12000} factor={6} saturation={0} fade speed={0.35} />
          <CameraRig />
        </Canvas>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_40%,rgba(0,0,0,0.65)_100%)]" />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-end gap-6 px-6 pb-[10vh] text-center text-white">
        <p className="max-w-md text-sm text-slate-300 sm:text-base">Cada memória vira uma estrela nesta galáxia.</p>
        <button
          type="button"
          onClick={onRevive}
          className="pointer-events-auto cursor-pointer rounded-full border border-white/20 bg-white/10 px-8 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-white backdrop-blur-md transition hover:scale-105 hover:border-yellow-300/60 hover:bg-yellow-300/10 hover:text-yellow-200"
        >
          Reviver experiência
        </button>
      </div>
    </section>
  );
}
