"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Canvas } from "@react-three/fiber";
import { Stars } from "@react-three/drei";

import CameraRig from "@/components/universe/CameraRig";
import { getAccessToken } from "@/lib/storage";
import { savePendingGalaxySave } from "@/lib/pendingGalaxySave";
import { saveExperienceToGalaxy } from "@/lib/publicExperience";
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
  // Etapa Minha Galáxia (destinatário): presente só no modo público
  // (ExperienceViewer's `experience` prop path — ver PublicExperienceView.tsx).
  // Sem ele (modo wizard/checkout), "Criar minha Galáxia" nunca é
  // oferecido — isOwner já é true por padrão nesse modo, então o visitante
  // já vê "Conhecer sua galáxia" em vez disso.
  slug?: string;
};

type GalaxySavePhase =
  | { kind: "idle" }
  // Não autenticado (ou token inválido/expirado): mostra o cartão "Criar
  // minha conta" / "Entrar" em vez de tentar salvar direto.
  | { kind: "choice" }
  | { kind: "saving" }
  | { kind: "saved" };

// The final screen of the public experience: rendered directly (no
// intermediate "Tem mais" step) as soon as the parent's chapter reaches
// "completed" — mounts its Canvas/WebGL context once, right here, and only
// ever this once per playthrough. "Conhecer sua galáxia" leaves the
// experience entirely (router.push, no second chapter/scene); "Reviver
// experiência" is the only way back into the story, and it works by the
// parent unmounting this whole component (chapter leaves "completed"),
// which tears the Canvas down cleanly via react-three-fiber.
export default function GalaxyChapter({ onRevive, isOwner, slug }: GalaxyChapterProps) {
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

  const [savePhase, setSavePhase] = useState<GalaxySavePhase>({ kind: "idle" });

  useEffect(() => {
    if (savePhase.kind !== "saved") return;
    const redirectTimer = window.setTimeout(() => router.push("/dashboard/galaxia"), 1400);
    return () => window.clearTimeout(redirectTimer);
  }, [savePhase, router]);

  async function handleCreateGalaxyClick() {
    if (!slug) return;

    // Checagem client-side só para decidir QUAL UI mostrar (cartão de
    // login/cadastro vs. tentar salvar direto) — nunca é a autorização de
    // verdade: o backend (IsAuthenticated em SaveExperienceToGalaxyView)
    // sempre revalida, e um token presente-mas-expirado ainda cai no catch
    // abaixo e volta para o cartão de login.
    if (!getAccessToken()) {
      setSavePhase({ kind: "choice" });
      return;
    }

    setSavePhase({ kind: "saving" });
    try {
      await saveExperienceToGalaxy(slug);
      setSavePhase({ kind: "saved" });
    } catch {
      // Token presente mas inválido/expirado (ex.: refresh falhou em
      // segundo plano) cai aqui também — melhor oferecer login de novo do
      // que uma mensagem de erro genérica sem saída.
      setSavePhase({ kind: "choice" });
    }
  }

  function goToAuth(path: "/register" | "/login") {
    if (slug) savePendingGalaxySave(slug);
    router.push(path);
  }

  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-black">
      <div className="absolute inset-0">
        <Canvas camera={{ position: [0, 0, 12], fov: 65 }}>
          <color attach="background" args={["#020617"]} />
          <ambientLight intensity={0.8} />
          <Stars radius={250} depth={80} count={12000} factor={6} saturation={0} fade speed={0.35} />
          <GalaxyTransition active phase={transitionPhase} />
          <CameraRig />
        </Canvas>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_40%,rgba(0,0,0,0.65)_100%)]" />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-end gap-6 px-6 pb-[10vh] text-center text-white">
        <p className="max-w-md text-sm text-slate-300 sm:text-base">Cada memória vira uma estrela nesta galáxia.</p>

        {savePhase.kind === "choice" && (
          <div className="pointer-events-auto flex w-full max-w-sm flex-col gap-4 rounded-3xl border border-white/10 bg-white/5 p-6 text-center backdrop-blur-xl">
            <div>
              <h2 className="text-lg font-bold text-white">Crie sua Galáxia</h2>
              <p className="mt-1 text-sm text-slate-300">Guarde esta experiência na sua própria Galáxia.</p>
            </div>
            <button
              type="button"
              onClick={() => goToAuth("/register")}
              className="cursor-pointer rounded-full bg-yellow-300 px-6 py-3 text-sm font-semibold uppercase tracking-[0.2em] text-slate-950 transition hover:scale-105 hover:bg-yellow-200"
            >
              Criar minha conta
            </button>
            <button
              type="button"
              onClick={() => goToAuth("/login")}
              className="cursor-pointer text-sm text-slate-300 underline-offset-4 transition hover:text-yellow-200 hover:underline"
            >
              Já possui uma conta? Entrar
            </button>
            <button
              type="button"
              onClick={() => setSavePhase({ kind: "idle" })}
              className="cursor-pointer text-xs text-slate-500 transition hover:text-slate-300"
            >
              Cancelar
            </button>
          </div>
        )}

        {savePhase.kind === "saving" && (
          <div className="pointer-events-auto flex items-center gap-3 rounded-full border border-white/10 bg-white/5 px-6 py-3 text-sm text-slate-300 backdrop-blur-xl">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-yellow-300/30 border-t-yellow-300" />
            Salvando na sua Galáxia...
          </div>
        )}

        {savePhase.kind === "saved" && (
          <div className="pointer-events-auto flex items-center gap-3 rounded-full border border-green-400/30 bg-green-400/10 px-6 py-3 text-sm font-semibold text-green-300">
            ✨ Salva na sua Galáxia! Levando você para lá...
          </div>
        )}

        {savePhase.kind === "idle" && (
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
            {!isOwner && slug && (
              <button
                type="button"
                onClick={handleCreateGalaxyClick}
                className="pointer-events-auto cursor-pointer rounded-full bg-yellow-300 px-8 py-4 text-sm font-semibold uppercase tracking-[0.2em] text-slate-950 transition hover:scale-105 hover:bg-yellow-200"
              >
                ✨ Criar minha Galáxia
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
        )}
      </div>
    </section>
  );
}
