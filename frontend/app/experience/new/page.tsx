import ExperienceBuilder from "@/components/experience/ExperienceBuilder";
import { ExperienceProvider } from "@/components/experience/context/ExperienceContext";

// Força renderização dinâmica — ver comentário em app/login/page.tsx (mesmo
// bug: nonce de CSP congelado no build em páginas estáticas, quebrando a
// hidratação de todo o wizard de criação de experiência).
export const dynamic = "force-dynamic";

export default function NewExperiencePage() {
  return (
    <ExperienceProvider>
      <main className="min-h-screen bg-slate-950 text-white">
        <ExperienceBuilder />
      </main>
    </ExperienceProvider>
  );
}