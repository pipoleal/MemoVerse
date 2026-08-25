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
import { getInformationStepConfig } from "./informationStepConfig";
import type { Experience } from "./types";

// Fase 2.1: cada campo de config.fields carrega seu próprio label — a
// mensagem de erro é derivada dele, nunca uma lista de `if` por campo. Só
// itera os campos do tipo atual (getInformationStepConfig já resolve o
// fallback pra tipo vazio/desconhecido — ver informationStepConfig.ts).
function missingRequiredFieldError(experience: Experience): string {
  const { fields } = getInformationStepConfig(experience.type);

  for (const field of fields) {
    if (!field.required) continue;
    if (experience[field.key].trim()) continue;
    return `Preencha o campo "${field.label}" para continuar.`;
  }

  return "";
}

export default function ExperienceBuilder() {
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");

  const { experience, updateExperience, syncDraftProgress, isLoadingInitialDraft, initialDraftLoadError } = useExperience();

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
      return missingRequiredFieldError(experience);
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

    // Etapa 7: persist progress on every forward transition — creates the
    // draft the first time there's real data to protect, and PATCHes
    // whatever's been filled so far on every step after that. Fire-and-forget
    // on purpose: navigation must never wait on this (see the type comment
    // on syncDraftProgress for the self-healing/retry rationale).
    void syncDraftProgress();

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

  // Etapa do scroll do Preview: o Preview precisa poder crescer além de uma
  // viewport (uma carta grande) e deixar a PÁGINA rolar normalmente — o que
  // é impossível enquanto StepIndicator/NavigationButtons continuam
  // montados ao redor dele, porque PreviewStep então precisa ficar `fixed`
  // só para cobri-los visualmente, e um elemento `fixed` nunca cresce com o
  // scroll da página (por definição, fica preso ao viewport). Retornar só
  // <PreviewStep /> aqui — sem StepIndicator, sem o <section> com
  // max-w-5xl/padding, sem NavigationButtons — é o que permite a
  // PreviewStep.tsx abandonar o `fixed inset-0` e virar um bloco normal que
  // cresce com o conteúdo. Visualmente idêntico a antes (esses elementos já
  // ficavam cobertos pelo overlay fixed do Preview; agora simplesmente não
  // são renderizados enquanto o Preview está ativo, em vez de escondidos
  // atrás dele).
  if (step === 8) {
    return <PreviewStep />;
  }

  return (
    <section className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-6 py-10">
      <StepIndicator step={step} />

      <div className="mt-10 flex-1">
        {step === 1 && (
          <TypeStep
            value={experience.type}
            onChange={(value) => {
              // Etapa 1 da correção de contaminação entre tipos: title/
              // shortMessage/contextAnswer são os únicos campos cujo
              // *sentido* é definido pelo tipo (ver informationStepConfig.ts)
              // — trocar de tipo sem limpá-los deixa a resposta de um
              // contexto (ex.: "Nosso Pedido de Namoro ❤️", "Eu sinto que...")
              // visível sob o rótulo de outro tipo. `letter` fica de fora de
              // propósito (ver instrução da tarefa) — o usuário pode ter
              // escrito uma carta que quer manter mesmo trocando o tipo. Só
              // limpa quando o tipo de fato muda (re-selecionar o mesmo tipo
              // é a não-mudança, nunca deve apagar nada).
              const changedType = value !== experience.type;

              updateExperience({
                type: value,
                ...(changedType
                  ? { title: "", shortMessage: "", contextAnswer: "" }
                  : {}),
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
      </div>

      <NavigationButtons
        step={step}
        onNext={nextStep}
        onPrevious={previousStep}
      />
    </section>
  );
}