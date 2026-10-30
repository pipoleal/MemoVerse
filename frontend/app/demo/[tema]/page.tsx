import type { Metadata } from "next";
import { notFound } from "next/navigation";

import DemoExperience from "./DemoExperience";

type PageProps = {
  params: Promise<{ tema: string }>;
};

// /demo/flores, /demo/universo... -> código do tema em lib/themeRegistry.ts.
const DEMO_THEMES: Record<string, string> = {
  flores: "flowers",
  universo: "universe",
  cinema: "cinema",
  praia: "beach",
  noite: "night",
  minimalista: "minimal",
};

// Página de demonstração, não de produto: fora dos buscadores.
export const metadata: Metadata = {
  title: "MemoVerse · Demonstração",
  robots: { index: false, follow: false },
};

export function generateStaticParams() {
  return Object.keys(DEMO_THEMES).map((tema) => ({ tema }));
}

export default async function DemoPage({ params }: PageProps) {
  const { tema } = await params;
  const theme = DEMO_THEMES[tema];
  if (!theme) notFound();

  return <DemoExperience theme={theme} />;
}
