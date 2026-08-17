"use client";

type StepIndicatorProps = {
  step: number;
};

const steps = [
  "Tipo",
  "Estilo",
  "Informações",
  "Fotos",
  "Vídeos",
  "Carta",
  "Música",
  "Preview",
];

export default function StepIndicator({
  step,
}: StepIndicatorProps) {
  return (
    <div className="hidden w-full items-center justify-between gap-2 pb-4 md:flex">
      {steps.map((stepName, index) => {
        const currentStep = index + 1;

        const active = step === currentStep;
        const completed = step > currentStep;

        return (
          <div
            key={stepName}
            className="flex shrink-0 items-center gap-3"
          >
            <div
              className={`
                flex h-10 w-10 items-center justify-center
                rounded-full border-2
                font-medium
                transition-all duration-300
                ${
                  completed
                    ? "border-yellow-400 bg-yellow-400 text-black"
                    : active
                      ? "border-yellow-400 bg-yellow-400/10 text-yellow-400"
                      : "border-white/20 text-slate-500"
                }
              `}
            >
              {completed ? "✓" : currentStep}
            </div>

            <span
              className={`
                text-sm transition-colors
                ${
                  active || completed
                    ? "text-white"
                    : "text-slate-500"
                }
              `}
            >
              {stepName}
            </span>

            {index !== steps.length - 1 && (
              <div
                className={`
                  h-0.5 w-8 transition-colors duration-300
                  ${
                    completed
                      ? "bg-yellow-400"
                      : "bg-white/10"
                  }
                `}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}