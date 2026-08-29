import ExperienceDetailView from "@/components/admin/ExperienceDetailView";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function AdminExperienceDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <ExperienceDetailView draftId={id} />;
}
