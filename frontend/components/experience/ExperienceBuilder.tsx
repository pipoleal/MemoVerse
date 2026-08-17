"use client";

import { useState } from "react";

import NavigationButtons from "./NavigationButtons";
import StepIndicator from "./StepIndicator";

import TypeStep from "./steps/TypeStep";
import StyleStep from "./steps/StyleStep";
import InformationStep from "./steps/InformationStep";
import PhotosStep from "./steps/PhotosStep";
import VideosStep from "./steps/VideosStep";
import LetterStep from "./steps/LetterStep";
import MusicStep from "./steps/MusicStep";
import PreviewStep from "./steps/PreviewStep";

import { useExperience } from "./context/ExperienceContext";

export default function ExperienceBuilder() {
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");

  const { experience, updateExperience, isLoadingInitialDraft, initialDraftLoadError } = useExperience();

  function validateCurrentStep() {
    if (step === 1) {
      if (!experience.type) {
        return "Escolha o tipo da experiência para continuar.";
      }
    }

    if (step === 2) {
      if (!experience.theme) {
        return "Escolha um estilo para continuar.";
      }
    }

    if (step === 3) {
      if (!experience.title.trim()) {
        return "Digite um título para sua experiência.";
      }

      if (!experience.recipient.trim()) {
        return "Informe para quem é essa experiência.";
      }

      if (!experience.creator.trim()) {
        return "Informe seu nome.";
      }

      if (!experience.eventDate) {
        return "Escolha uma data especial.";
      }
    }

    return "";
  }

  function nextStep() {
    const validationError = validateCurrentStep();

    if (validationError) {
      setError(validationError);
      return;
    }

    setError("");

    setStep((current) => Math.min(current + 1, 8));
  }

  function previousStep() {
    setError("");

    setStep((current) => Math.max(current - 1, 1));
  }

  if (isLoadingInitialDraft) {
    return (
      <section className="flex min-h-screen w-full flex-col items-center justify-center gap-4 px-6 py-10 text-white">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
        <p className="text-slate-300">Carregando sua experiência...</p>
      </section>
    );
  }

  if (initialDraftLoadError) {
    return (
      <section className="flex min-h-screen w-full flex-col items-center justify-center gap-4 px-6 py-10 text-center text-white">
        <span className="text-5xl">⚠</span>
        <p className="max-w-md text-slate-300">{initialDraftLoadError}</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
        >
          Tentar novamente
        </button>
      </section>
    );
  }

  return (
    <section className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-6 py-10">
      <StepIndicator step={step} />

      <div className="mt-10 flex-1">
        {step === 1 && (
          <TypeStep
            value={experience.type}
            onChange={(value) => {
              updateExperience({
                type: value,
              });

              setError("");
            }}
          />
        )}

        {step === 2 && <StyleStep />}

        {step === 3 && (
          <InformationStep error={error} />
        )}

        {step === 4 && <PhotosStep />}

        {step === 5 && <VideosStep />}

        {step === 6 && <LetterStep />}

        {step === 7 && <MusicStep />}

        {step === 8 && <PreviewStep />}
      </div>

      <NavigationButtons
        step={step}
        onNext={nextStep}
        onPrevious={previousStep}
      />
    </section>
  );
}