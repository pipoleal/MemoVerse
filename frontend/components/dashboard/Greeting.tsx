"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { getUserFirstName } from "@/lib/storage";

type FadeInProps = {
  children: ReactNode;
  delay?: number;
};

function FadeIn({ children, delay = 0 }: FadeInProps) {
  return (
    <div
      style={{
        opacity: 1,
        transform: "translateY(0)",
        transition: `opacity 0.6s ease ${delay}s, transform 0.6s ease ${delay}s`,
      }}
    >
      {children}
    </div>
  );
}

export default function Greeting() {
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    setName(getUserFirstName());
  }, []);

  return (
    <FadeIn delay={0.2}>
      <div className="space-y-3">

        <p className="uppercase tracking-[0.35em] text-yellow-400 text-sm">
          Bem-vindo de volta
        </p>

        <h1 className="text-5xl font-black bg-linear-to-r from-white via-slate-200 to-yellow-300 bg-clip-text text-transparent">
          {name ?? "Viajante"}
        </h1>

        <p className="max-w-xl text-slate-300 text-lg">
          Cada memória criada ilumina uma nova estrela no seu universo.
        </p>

      </div>
    </FadeIn>
  );
}