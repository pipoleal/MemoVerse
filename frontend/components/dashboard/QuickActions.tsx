"use client";

import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";

export default function QuickActions() {
  const router = useRouter();

  return (
    <FadeIn delay={0.5}>
      <div className="mt-10 flex flex-col gap-4 sm:flex-row">

        <Button
          className="flex-1 py-5 text-lg"
          onClick={() => router.push("/experience/new")}
        >
          ✨ Criar Nova Experiência
        </Button>

        <Button
          variant="secondary"
          className="flex-1 py-5 text-lg disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:scale-100 disabled:hover:translate-y-0"
          disabled
          title="Em breve"
        >
          🌌 Minha Galáxia
        </Button>

      </div>
    </FadeIn>
  );
}