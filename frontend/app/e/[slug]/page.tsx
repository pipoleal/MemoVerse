import type { Metadata } from "next";
import PublicExperienceView from "@/components/public/PublicExperienceView";

type PageProps = {
  params: Promise<{ slug: string }>;
};

// Deliberately not reusing lib/publicExperience.ts / lib/api.ts here: both
// pull in lib/storage.ts, which touches localStorage unconditionally. That's
// fine in the browser, but generateMetadata runs on the server (Node) —
// importing it there would throw. This mirrors only the few response fields
// this function actually needs, straight from
// apps.experiences.serializers.PublicExperienceSerializer.
type ExperienceMetadataSource = {
  title: string;
  recipient_name: string;
  short_message: string;
  media: { media_type: string; url: string; sort_order: number }[];
};

async function fetchExperienceForMetadata(slug: string): Promise<ExperienceMetadataSource | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";
  try {
    const response = await fetch(`${apiUrl}/public/experiences/${slug}/`, {
      // Public experience content (photos, letter) can change any time
      // before a fixed cache would expire — no caching keeps a shared
      // link's preview accurate.
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as ExperienceMetadataSource;
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const experience = await fetchExperienceForMetadata(slug);

  // Unpublished/unknown slug, or the backend unreachable — generic
  // MemoVerse metadata instead of failing the page over an SEO extra.
  if (!experience) {
    return { title: "MemoVerse" };
  }

  const title = experience.title?.trim() || `Uma mensagem especial para ${experience.recipient_name}`;
  const description = experience.short_message?.trim() || "Uma experiência criada com carinho no MemoVerse.";
  const firstPhoto = [...experience.media]
    .filter((item) => item.media_type === "photo" && item.url)
    .sort((a, b) => a.sort_order - b.sort_order)[0];

  return {
    title,
    description,
    openGraph: {
      // Next.js replaces the parent's `openGraph` object wholesale rather
      // than merging individual fields — siteName/locale/type from
      // app/layout.tsx would otherwise silently disappear on this page.
      siteName: "MemoVerse",
      locale: "pt_BR",
      type: "website",
      title,
      description,
      images: firstPhoto ? [{ url: firstPhoto.url }] : undefined,
    },
  };
}

export default async function PublicExperiencePage({ params }: PageProps) {
  const { slug } = await params;

  return <PublicExperienceView slug={slug} />;
}
