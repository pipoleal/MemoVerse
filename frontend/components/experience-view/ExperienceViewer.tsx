"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import { useOptionalExperience } from "../experience/context/ExperienceContext";
import type { Experience } from "../experience/types";
import { getThemeVisual } from "@/lib/themeRegistry";

import GalaxyChapter from "./scenes/GalaxyChapter";
import LetterChapter from "./scenes/LetterChapter";
import PlanetScene from "./scenes/PlanetScene";
import RecipientRevealChapter from "./scenes/RecipientRevealChapter";
import MemoriesCanvas from "./MemoriesCanvas";
import MusicPlayer from "./MusicPlayer";

export type ExperienceChapter =
  | "idle"
  | "signature-opening"
  | "recipient-reveal"
  | "letter"
  | "memories"
  | "closing"
  | "completed";

type ExperienceRuntimeEvent =
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
};

export default function ExperienceViewer({ experience: experienceProp, onCompleted, isOwner = true }: ExperienceViewerProps) {
  // useOptionalExperience (not useExperience) never throws when there is no
  // Provider — required so the prop-driven mode above can mount without one.
  const context = useOptionalExperience();
  const experience = experienceProp ?? context?.experience;

  const [chapter, setChapter] =
    useState<ExperienceChapter>("idle");
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

  // Resolved once here and handed only to the two surfaces that were ever
  // themed to begin with (Memórias/Fotos and a Carta) — the opening,
  // revelação and encerramento keep MemoVerse's shared spatial identity
  // regardless of theme; see MemoriesCanvas/LetterChapter below.
  // Unknown/legacy/empty theme values never break this — getThemeVisual()
  // always falls back to a complete definition (see lib/themeRegistry.ts).
  const visual = getThemeVisual(experience.theme);

  return (
    <main className="relative min-h-screen w-full overflow-hidden bg-black">
      <MusicPlayer
        key={reviveCount}
        provider={experience.music.provider}
        url={experience.music.url}
        playing={hasInteracted}
      />

      <AnimatePresence mode="sync" initial={false}>
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
              onComplete={() => {
                send("RECIPIENT_COMPLETE");
              }}
            />
          </motion.div>
        )}

        {chapter === "letter" && (
          <motion.div
            key="letter"
            className="absolute inset-0"
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
              theme={visual}
              shortMessage={experience.shortMessage}
              photos={experience.photos}
              videos={experience.videos}
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
            <GalaxyChapter onRevive={handleRevive} isOwner={isOwner} />
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
