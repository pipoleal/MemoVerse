import PublicExperienceView from "@/components/public/PublicExperienceView";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export default async function PublicExperiencePage({ params }: PageProps) {
  const { slug } = await params;

  return <PublicExperienceView slug={slug} />;
}
