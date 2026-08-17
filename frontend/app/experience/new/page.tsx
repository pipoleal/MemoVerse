import ExperienceBuilder from "@/components/experience/ExperienceBuilder";
import { ExperienceProvider } from "@/components/experience/context/ExperienceContext";

export default function NewExperiencePage() {
  return (
    <ExperienceProvider>
      <main className="min-h-screen bg-slate-950 text-white">
        <ExperienceBuilder />
      </main>
    </ExperienceProvider>
  );
}