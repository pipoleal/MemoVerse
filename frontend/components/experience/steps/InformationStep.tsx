"use client";

import FadeIn from "../../animations/FadeIn";
import Field from "../../ui/forms/Field";
import Input from "../../ui/forms/Input";
import Textarea from "../../ui/forms/Textarea";
import DateInput from "../../ui/forms/DateInput";
import { useExperience } from "../context/ExperienceContext";

type InformationStepProps = {
  error?: string;
};

export default function InformationStep({
  error,
}: InformationStepProps) {
  const { experience, updateExperience } = useExperience();

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
          <Field
            label="Título da experiência"
            description="Dê um nome especial para essa experiência."
          >
            <Input
              value={experience.title}
              onChange={(event) =>
                updateExperience({
                  title: event.target.value,
                })
              }
              placeholder="Nosso Pedido de Namoro ❤️"
            />
          </Field>

          <Field
            label="Para quem é?"
            description="A pessoa que receberá essa experiência."
          >
            <Input
              value={experience.recipient}
              onChange={(event) =>
                updateExperience({
                  recipient: event.target.value,
                })
              }
              placeholder="Nome de quem receberá"
            />
          </Field>

          <Field
            label="Seu nome"
            description="Como você gostaria de aparecer na experiência?"
          >
            <Input
              value={experience.creator}
              onChange={(event) =>
                updateExperience({
                  creator: event.target.value,
                })
              }
              placeholder="Seu nome"
            />
          </Field>

          <Field
            label="Data especial"
            description="A data que representa esse momento."
          >
            <DateInput
              value={experience.eventDate}
              onChange={(event) =>
                updateExperience({
                  eventDate: event.target.value,
                })
              }
            />
          </Field>

          <Field
            label="Uma mensagem curta"
            description="Opcional. Uma frase para dar ainda mais personalidade à experiência."
          >
            <Textarea
              value={experience.shortMessage}
              onChange={(event) =>
                updateExperience({
                  shortMessage: event.target.value,
                })
              }
              placeholder="Toda estrela tem uma história. A nossa começou aqui..."
              rows={4}
            />
          </Field>
        </div>
      </section>
    </FadeIn>
  );
}