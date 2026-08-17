"use client";

import { useRouter } from "next/navigation";

import { useExperience } from "./context/ExperienceContext";
import { savePendingExperience } from "@/lib/pendingExperience";

export default function ExperienceCompletion() {
  const router = useRouter();
  const { experience } = useExperience();

  function continueTo(path: "/register" | "/login") {
    savePendingExperience(experience);
    router.push(path);
  }

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#040612] px-6 text-center text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(217,180,75,0.18),transparent_40%)]" />
      <div className="relative w-full max-w-xl rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-xl sm:p-12">
        <p className="text-sm font-semibold uppercase tracking-[0.3em] text-yellow-300">MemoVerse</p>
        <h1 className="mt-5 text-4xl font-semibold tracking-tight sm:text-5xl">Sua galáxia está pronta.</h1>
        <p className="mt-5 text-base leading-relaxed text-slate-300 sm:text-lg">Crie sua conta para guardar esta experiência e continuar.</p>
        <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button type="button" onClick={() => continueTo("/register")} className="rounded-full bg-yellow-300 px-6 py-3 font-semibold text-slate-950 transition hover:bg-yellow-200">Criar minha conta</button>
          <button type="button" onClick={() => continueTo("/login")} className="rounded-full border border-white/20 px-6 py-3 font-semibold text-white transition hover:bg-white/10">Já tenho uma conta</button>
        </div>
      </div>
    </section>
  );
}
