"use client";

import Button from "../ui/Button";

type Props = {
  step: number;
  onNext: () => void;
  onPrevious: () => void;
};

export default function NavigationButtons({
  step,
  onNext,
  onPrevious,
}: Props) {
  return (
    <div className="mt-12 flex justify-between">
      <Button
        variant="secondary"
        onClick={onPrevious}
        disabled={step === 1}
      >
        ← Voltar
      </Button>

      <Button
        onClick={onNext}
      >
        Próximo →
      </Button>
    </div>
  );
}