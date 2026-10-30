"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, MotionConfig, motion } from "framer-motion";

import { useOptionalExperience } from "../experience/context/ExperienceContext";
import { getInformationStepConfig } from "../experience/informationStepConfig";
import type { Experience } from "../experience/types";
import { experienceThemeStyle, getThemeVisual } from "@/lib/themeRegistry";
import { experienceSerif } from "@/lib/experienceFonts";

import GalaxyChapter from "./scenes/GalaxyChapter";
import PreviewChapter from "./scenes/PreviewChapter";
import LetterChapter from "./scenes/LetterChapter";
import PlanetScene from "./scenes/PlanetScene";
import RecipientRevealChapter from "./scenes/RecipientRevealChapter";
import MemoriesCanvas from "./MemoriesCanvas";
import MusicPlayer from "./MusicPlayer";
import ThemeParticles from "./theme/ThemeParticles";

export type ExperienceChapter =
  | "preview"
  | "idle"
  | "signature-opening"
  | "recipient-reveal"
  | "letter"
  | "memories"
  | "closing"
  | "completed";

type ExperienceRuntimeEvent =
  | "PREVIEW_COMPLETE"
  | "START_EXPERIENCE"
  | "SIGNATURE_COMPLETE"
  | "RECIPIENT_COMPLETE"
  | "LETTER_COMPLETE"
  | "MEMORIES_COMPLETE"
  | "CLOSING_COMPLETE";

// Duração compartilhada do crossfade entre capítulos — mesmo valor que já
// era usado na saída da carta, agora aplicado por uma camada única.
const CHAPTER_TRANSITION = { duration: 0.7, ease: "easeInOut" } as const;

type ExperienceViewerProps = {
  // When provided, this experience is rendered as-is and the component does
  // NOT touch ExperienceContext at all — the wizard's ExperienceProvider is
  // not required in this mode (e.g. the future public page /e/[slug],
  // rendering an Experience fetched from the API). When omitted, the
  // component falls back to the wizard's context, exactly as before —
  // ExperienceProvider is then required, same as today.
  experience?: Experience;
  onCompleted?: () => void;
  // Controls whether GalaxyChapter's "Conhecer sua galáxia" button is shown
  // (see that component) — true by default because the wizard/checkout mode
  // above (no `experience` prop, context-driven) only ever renders for the
  // authenticated draft owner. The public page (`experience` prop set, see
  // PublicExperienceView.tsx) always passes this explicitly, since a
  // visitor there may or may not be the owner.
  isOwner?: boolean;
  // Etapa Minha Galáxia (destinatário): o slug público desta experiência —
  // só o suficiente para GalaxyChapter chamar "Criar minha Galáxia"
  // (POST /experiences/public/<slug>/save/), nunca guardado em
  // Experience/toExperience (aquele tipo descreve a experiência em si, não
  // sua identidade pública). undefined no modo wizard/checkout (sem
  // `experience` prop) — lá o botão nunca é mostrado de qualquer forma,
  // porque isOwner já é true por padrão nesse modo.
  slug?: string;
};

export default function ExperienceViewer({ experience: experienceProp, onCompleted, isOwner = true, slug }: ExperienceViewerProps) {
  // useOptionalExperience (not useExperience) never throws when there is no
  // Provider — required so the prop-driven mode above can mount without one.
  const context = useOptionalExperience();
  const experience = experienceProp ?? context?.experience;

  const [chapter, setChapter] =
    useState<ExperienceChapter>("preview");
  const [hasInteracted, setHasInteracted] = useState(false);
  // Bumped by "Reviver experiência" only, to force MusicPlayer to remount so
  // its YouTube player restarts from 0 instead of resuming where it left
  // off. Nothing else needs this: every chapter block below is only
  // rendered while `chapter` matches it, so sending `chapter` back to
  // "idle" already unmounts/remounts each one (PlanetScene, MemoriesCanvas,
  // GalaxyChapter's own Canvas/WebGL context included) with fresh state for
  // free — no extra key required there.
  const [reviveCount, setReviveCount] = useState(0);

  const send = useCallback((event: ExperienceRuntimeEvent) => {
    setChapter((currentChapter) => {
      if (event === "PREVIEW_COMPLETE" && currentChapter === "preview") {
        return "idle";
      }

      if (event === "START_EXPERIENCE" && currentChapter === "idle") {
        return "signature-opening";
      }

      if (event === "SIGNATURE_COMPLETE" && currentChapter === "signature-opening") {
        return "recipient-reveal";
      }

      if (event === "RECIPIENT_COMPLETE" && currentChapter === "recipient-reveal") {
        return "letter";
      }

      if (event === "LETTER_COMPLETE" && currentChapter === "letter") {
        return "memories";
      }

      if (event === "MEMORIES_COMPLETE" && currentChapter === "memories") {
        return "closing";
      }

      if (event === "CLOSING_COMPLETE" && currentChapter === "closing") {
        return "completed";
      }

      return currentChapter;
    });
  }, []);

  useEffect(() => {
    if (chapter !== "closing") return;
    const completionTimer = window.setTimeout(() => send("CLOSING_COMPLETE"), 1200);
    return () => window.clearTimeout(completionTimer);
  }, [chapter, send]);

  useEffect(() => {
    if (chapter === "completed") onCompleted?.();
  }, [chapter, onCompleted]);

  function handleRevive() {
    setHasInteracted(false);
    setChapter("idle");
    setReviveCount((count) => count + 1);
  }

  if (!experience) {
    // Neither an `experience` prop nor an ExperienceProvider ancestor was
    // found — same fail-fast guarantee useExperience() gave before this
    // refactor, just reachable from either mode now instead of only one.
    throw new Error(
      "ExperienceViewer precisa de uma prop `experience` ou de um ExperienceProvider ancestral."
    );
  }

  const isSignatureChapter =
    chapter === "idle" ||
    chapter === "signature-opening";

  // Redesign "Fluxo da experiência": todas as 7 telas (Prévia → Fotos) são
  // do tema agora — os tokens viram variáveis CSS na raiz (<main> abaixo) e
  // cada capítulo só lê essas variáveis. Só o encerramento (GalaxyChapter)
  // continua com a identidade espacial própria do MemoVerse.
  // Unknown/legacy/empty theme values never break this — getThemeVisual()
  // always falls back to a complete definition (see lib/themeRegistry.ts).
  const visual = getThemeVisual(experience.theme);
  const tokens = visual.experience;
  const hasMusic = experience.music.provider !== "none" && Boolean(experience.music.url);

  // Partículas do tema (pétalas no Flores...) em todas as telas, menos na
  // abertura cósmica (Começar, que já tem o próprio campo de estrelas) e no
  // encerramento WebGL.
  const showParticles =
    chapter === "preview" ||
    chapter === "recipient-reveal" ||
    chapter === "letter" ||
    chapter === "memories";

  // Polimento do Preview — Problema 2: a pergunta mostrada junto da resposta
  // em LetterChapter é sempre a mesma pergunta que InformationStep já exibiu
  // para este tipo (ver informationStepConfig.ts, única fonte de verdade das
  // perguntas por tipo) — nunca uma segunda cópia hardcoded aqui, e nunca um
  // `if (experience.type === ...)`. undefined para "custom" (o único tipo
  // sem essa pergunta) ou para um tipo desconhecido/legado; LetterChapter cai
  // para um rótulo genérico nesse caso.
  const contextQuestion = getInformationStepConfig(experience.type).fields.find(
    (field) => field.key === "contextAnswer"
  )?.label;

  return (
    // Etapa do scroll do Preview: sem overflow-hidden aqui — os outros
    // capítulos (absolute inset-0) não dependem disso pra se conter (cada
    // um já se auto-clipa na própria raiz — ver PlanetScene/
    // RecipientRevealChapter/GalaxyChapter/MemoriesCanvas), e o capítulo da
    // carta precisa poder crescer além de uma viewport sem ser cortado
    // aqui.
    // MotionConfig reducedMotion="user": toda animação framer-motion abaixo
    // respeita prefers-reduced-motion sem precisar checar em cada capítulo.
    <MotionConfig reducedMotion="user">
      <main
        className={`mv-root relative min-h-screen w-full bg-black ${experienceSerif.variable}`}
        style={experienceThemeStyle(visual)}
      >
        <MusicPlayer
          key={reviveCount}
          provider={experience.music.provider}
          url={experience.music.url}
          playing={hasInteracted}
        />

        {showParticles && <ThemeParticles kind={tokens.particles} />}

        <AnimatePresence mode="sync" initial={false}>
          {chapter === "preview" && (
            <motion.div
              key="preview"
              // Rola por conta própria se o cartão não couber numa tela
              // pequena (celular deitado).
              className="absolute inset-0 overflow-y-auto"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={CHAPTER_TRANSITION}
            >
              <PreviewChapter
                recipient={experience.recipient || "Você"}
                letter={experience.letter}
                seal={tokens.seal}
                divider={tokens.divider}
                onContinue={() => {
                  send("PREVIEW_COMPLETE");
                }}
              />
            </motion.div>
          )}

          {isSignatureChapter && (
            <motion.div
              key="opening"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={CHAPTER_TRANSITION}
            >
              <PlanetScene
                onStart={() => {
                  setHasInteracted(true);
                  send("START_EXPERIENCE");
                }}
                onStarsComplete={() => {
                  send("SIGNATURE_COMPLETE");
                }}
                started={chapter === "signature-opening"}
                hasMusic={hasMusic}
              />
            </motion.div>
          )}

          {chapter === "recipient-reveal" && (
            <motion.div
              key="recipient-reveal"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={CHAPTER_TRANSITION}
            >
              <RecipientRevealChapter
                title={experience.title || "Nossa história"}
                recipient={experience.recipient || "Você"}
                ornament={tokens.ornament}
                divider={tokens.divider}
                onComplete={() => {
                  send("RECIPIENT_COMPLETE");
                }}
              />
            </motion.div>
          )}

          {chapter === "letter" && (
            <motion.div
              key="letter"
              // Etapa do scroll do Preview: único capítulo que NÃO é
              // `absolute inset-0` (todos os outros continuam pinados
              // exatamente a uma viewport, sem scroll, de propósito — nada
              // muda neles). Este precisa participar do fluxo normal do
              // documento para que uma carta grande empurre a altura real de
              // `main`/da página, em vez de ficar preso a uma altura fixa.
              className="relative w-full"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={CHAPTER_TRANSITION}
            >
              <LetterChapter
                recipient={experience.recipient || "Você"}
                creator={experience.creator}
                letter={experience.letter}
                theme={experience.theme}
                eventDate={experience.eventDate}
                contextAnswer={experience.contextAnswer}
                contextQuestion={contextQuestion}
                onComplete={() => {
                  send("LETTER_COMPLETE");
                }}
              />
            </motion.div>
          )}

          {chapter === "memories" && (
            <motion.div
              key="memories"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={CHAPTER_TRANSITION}
            >
              <MemoriesCanvas
                shortMessage={experience.shortMessage}
                recipient={experience.recipient || "Você"}
                eventDate={experience.eventDate}
                photos={experience.photos}
                videos={experience.videos}
                slug={slug}
                onComplete={() => {
                  send("MEMORIES_COMPLETE");
                }}
              />
            </motion.div>
          )}

          {chapter === "completed" && (
            <motion.div
              key="completed"
              className="absolute inset-0"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={CHAPTER_TRANSITION}
            >
              <GalaxyChapter onRevive={handleRevive} isOwner={isOwner} slug={slug} />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </MotionConfig>
  );
}
