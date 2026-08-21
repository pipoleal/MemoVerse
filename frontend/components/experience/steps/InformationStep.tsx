"use client";

import FadeIn from "../../animations/FadeIn";
import Field from "../../ui/forms/Field";
import Input from "../../ui/forms/Input";
import Textarea from "../../ui/forms/Textarea";
import DateInput from "../../ui/forms/DateInput";
import { useExperience } from "../context/ExperienceContext";
import { getInformationStepConfig, type InformationField } from "../informationStepConfig";
import type { Experience } from "../types";

type InformationStepProps = {
  error?: string;
};

// Fase 2.1: renderiza os campos de config.fields (ver informationStepConfig.ts)
// — nunca um `if (type === "...")` aqui. Novo tipo ou pergunta = editar só
// o registry, este componente não muda.
function InformationFieldControl({
  field,
  experience,
  updateExperience,
}: {
  field: InformationField;
  experience: Experience;
  updateExperience: (data: Partial<Experience>) => void;
}) {
  const value = experience[field.key];

  function handleChange(newValue: string) {
    // field.key é sempre uma das 6 chaves string de Experience (ver
    // InformationFieldKey em informationStepConfig.ts) — a asserção só
    // recupera o que a indexação computada por si só perde de tipo.
    updateExperience({ [field.key]: newValue } as Partial<Experience>);
  }

  return (
    <Field label={field.label} description={field.description}>
      {field.component === "date" && (
        <DateInput value={value} onChange={(event) => handleChange(event.target.value)} />
      )}

      {field.component === "input" && (
        <Input
          value={value}
          onChange={(event) => handleChange(event.target.value)}
          placeholder={field.placeholder}
        />
      )}

      {field.component === "textarea" && (
        <Textarea
          value={value}
          onChange={(event) => handleChange(event.target.value)}
          placeholder={field.placeholder}
          rows={field.rows ?? 4}
        />
      )}
    </Field>
  );
}

export default function InformationStep({
  error,
}: InformationStepProps) {
  const { experience, updateExperience } = useExperience();
  const config = getInformationStepConfig(experience.type);

  return (
    <FadeIn>
      <section>
        <span className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          Etapa 3
        </span>

        <h1 className="mt-3 bg-linear-to-r from-white to-yellow-300 bg-clip-text text-5xl font-black text-transparent">
          Conte-nos sobre essa história
        </h1>

        <p className="mt-5 max-w-2xl text-slate-300">
          Algumas informações para começarmos a construir sua experiência.
        </p>

        {error && (
          <div className="mt-8 rounded-2xl border border-red-400/30 bg-red-400/10 px-5 py-4 text-sm text-red-200">
            {error}
          </div>
        )}

        <div className="mt-12 space-y-8">
          {config.fields.map((field) => (
            <InformationFieldControl
              key={field.key}
              field={field}
              experience={experience}
              updateExperience={updateExperience}
            />
          ))}
        </div>
      </section>
    </FadeIn>
  );
}
