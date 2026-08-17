import ExperienceBuilder from "@/components/experience/ExperienceBuilder";
import { ExperienceProvider } from "@/components/experience/context/ExperienceContext";

type PageProps = {
  params: Promise<{ draftId: string }>;
};

export default async function EditExperiencePage({ params }: PageProps) {
  const { draftId } = await params;

  return (
    <ExperienceProvider initialDraftId={draftId}>
      <main className="min-h-screen bg-slate-950 text-white">
        <ExperienceBuilder />
      </main>
    </ExperienceProvider>
  );
}
