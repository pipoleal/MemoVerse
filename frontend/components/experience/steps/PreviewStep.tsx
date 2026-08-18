"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import ExperienceViewer from "../../experience-view/ExperienceViewer";
import ExperienceCompletion from "../ExperienceCompletion";
import { useExperience } from "../context/ExperienceContext";
import { getAccessToken } from "@/lib/storage";
import { api } from "@/lib/api";
import { toPayload } from "@/lib/pendingExperience";

export default function PreviewStep() {
  const [completed, setCompleted] = useState(false);
  const [redirectingToCheckout, setRedirectingToCheckout] = useState(false);
  const [syncError, setSyncError] = useState("");
  const router = useRouter();
  const { experience, ensureDraftId } = useExperience();

  async function handleCompleted() {
    // Already authenticated (e.g. came from the dashboard's "Criar Nova
    // Experiência", wired up in an earlier task): skip the register/login
    // prompt entirely and go straight to checkout. Anonymous visitors keep
    // the existing register/login completion screen — checkout requires
    // auth anyway, and that hand-off flow is out of scope here.
    if (getAccessToken()) {
      setRedirectingToCheckout(true);
      setSyncError("");
      const draftId = await ensureDraftId();
      if (draftId) {
        // ensureDraftId only POSTs once, at whichever step first needs a
        // draft (a photo/video upload, or reaching here) — steps filled in
        // afterwards (e.g. Letter, Music) only ever update local context
        // state. Without this PATCH, anything edited after that first POST
        // is shown correctly in the wizard but never reaches the backend,
        // so it silently never survives publication. This must block
        // checkout on failure (not swallow it) — proceeding with stale
        // data would mean paying for an experience missing its own
        // content, exactly the bug this fixes.
        try {
          await api.patch(`/experiences/drafts/${draftId}/`, toPayload(experience));
        } catch {
          setSyncError(
            "Não foi possível salvar suas últimas alterações. Verifique sua conexão e tente novamente."
          );
          setRedirectingToCheckout(false);
          return;
        }
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
        <>
          {syncError && (
            <div className="absolute inset-x-0 top-6 z-10 mx-auto w-fit rounded-2xl border border-red-400/30 bg-red-500/10 px-5 py-3 text-sm text-red-200">
              {syncError}
            </div>
          )}
          <ExperienceViewer onCompleted={handleCompleted} />
        </>
      )}
    </div>
  );
}
