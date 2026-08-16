"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import ExperienceViewer from "../../experience-view/ExperienceViewer";
import ExperienceCompletion from "../ExperienceCompletion";
import { useExperience } from "../context/ExperienceContext";
import { getAccessToken } from "@/lib/storage";

export default function PreviewStep() {
  const [completed, setCompleted] = useState(false);
  const [redirectingToCheckout, setRedirectingToCheckout] = useState(false);
  const router = useRouter();
  const { ensureDraftId } = useExperience();

  async function handleCompleted() {
    // Already authenticated (e.g. came from the dashboard's "Criar Nova
    // Experiência", wired up in an earlier task): skip the register/login
    // prompt entirely and go straight to checkout. Anonymous visitors keep
    // the existing register/login completion screen — checkout requires
    // auth anyway, and that hand-off flow is out of scope here.
    if (getAccessToken()) {
      setRedirectingToCheckout(true);
      const draftId = await ensureDraftId();
      if (draftId) {
        router.push(`/checkout/${draftId}`);
        return;
      }
      // ensureDraftId failed even though a token exists (e.g. a network
      // blip) — fall back to the existing completion screen rather than
      // stranding the user on a dead loading state.
      setRedirectingToCheckout(false);
    }

    setCompleted(true);
  }

  return (
    <div className="fixed inset-0 z-50 h-screen w-screen overflow-hidden bg-black">
      {redirectingToCheckout ? (
        <div className="flex h-full w-full items-center justify-center text-white">
          <div className="flex flex-col items-center gap-4">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
            <p className="text-slate-300">Preparando o pagamento...</p>
          </div>
        </div>
      ) : completed ? (
        <ExperienceCompletion />
      ) : (
        <ExperienceViewer onCompleted={handleCompleted} />
      )}
    </div>
  );
}
