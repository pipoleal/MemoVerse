"use client";

import { useRouter } from "next/navigation";

import { cormorant } from "@/lib/fonts";
import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";

export default function FinalCta() {
  const router = useRouter();

  return (
    <section className="px-6 py-24 text-center sm:py-32">
      <FadeIn>
        <h2 className={`${cormorant.className} text-3xl italic text-white sm:text-5xl`}>
          Cada memória, um universo.
        </h2>
        <p className="mx-auto mt-5 max-w-md text-slate-400">
          Comece agora e transforme um momento especial em uma experiência inesquecível.
        </p>
        <div className="mt-10 flex justify-center">
          <Button variant="primary" onClick={() => router.push("/experience/new")}>
            ⭐ Criar minha experiência
          </Button>
        </div>
      </FadeIn>
    </section>
  );
}
