"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Canvas } from "@react-three/fiber";
import { Stars } from "@react-three/drei";

import CameraRig from "@/components/universe/CameraRig";
import ShootingStars from "@/components/universe/ShootingStars";
import GalaxyTransition from "../GalaxyTransition";

type GalaxyChapterProps = {
  onRevive: () => void;
  // Only the authenticated creator of this experience sees "Conhecer sua
  // galáxia" (it leads to their own /dashboard/galaxia) — a visitor who
  // opened a shared link has nothing of their own to be taken to there, so
  // the button is omitted entirely rather than shown and going somewhere
  // meaningless. See ExperienceViewer's isOwner prop and
  // PublicExperienceView.tsx (viewer_can_manage from the backend) for where
  // this is actually decided.
  isOwner: boolean;
};

// The final screen of the public experience: rendered directly (no
// intermediate "Tem mais" step) as soon as the parent's chapter reaches
// "completed" — mounts its Canvas/WebGL context once, right here, and only
// ever this once per playthrough. "Conhecer sua galáxia" leaves the
// experience entirely (router.push, no second chapter/scene); "Reviver
// experiência" is the only way back into the story, and it works by the
// parent unmounting this whole component (chapter leaves "completed"),
// which tears the Canvas down cleanly via react-three-fiber.
export default function GalaxyChapter({ onRevive, isOwner }: GalaxyChapterProps) {
  const router = useRouter();

  // Own entrance beat, independent of the theme (this chapter never reads
  // experience.theme — its identity is the Galaxy's own, not the
  // experience's): starts as a loose particle cloud (GalaxyTransition's
  // "particles" phase) and settles into the spiral "galaxy" phase a moment
  // later, once per mount — resets for free every time this component
  // remounts (see the comment above on "Reviver experiência").
  const [transitionPhase, setTransitionPhase] = useState<"particles" | "galaxy">("particles");

  useEffect(() => {
    const settleTimer = window.setTimeout(() => setTransitionPhase("galaxy"), 1600);
    return () => window.clearTimeout(settleTimer);
  }, []);

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-black">
      <div className="absolute inset-0">
        <Canvas camera={{ position: [0, 0, 12], fov: 65 }}>
          <color attach="background" args={["#020617"]} />
          <ambientLight intensity={0.8} />
          <Stars radius={250} depth={80} count={12000} factor={6} saturation={0} fade speed={0.35} />
          <GalaxyTransition active phase={transitionPhase} />
          <ShootingStars />
          <CameraRig />
        </Canvas>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_40%,rgba(0,0,0,0.65)_100%)]" />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-end gap-6 px-6 pb-[10vh] text-center text-white">
        <p className="max-w-md text-sm text-slate-300 sm:text-base">Cada memória vira uma estrela nesta galáxia.</p>
        <div className="flex flex-col gap-3 sm:flex-row">
          {isOwner && (
            <button
              type="button"
              onClick={() => router.push("/dashboard/galaxia")}
              className="pointer-events-auto cursor-pointer rounded-full bg-yellow-300 px-8 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-950 transition hover:scale-105 hover:bg-yellow-200"
            >
              ✨ Conhecer sua galáxia
            </button>
          )}
          <button
            type="button"
            onClick={onRevive}
            className="pointer-events-auto cursor-pointer rounded-full border border-white/20 bg-white/10 px-8 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-white backdrop-blur-md transition hover:scale-105 hover:border-yellow-300/60 hover:bg-yellow-300/10 hover:text-yellow-200"
          >
            ↻ Reviver experiência
          </button>
        </div>
      </div>
    </section>
  );
}
