import type { Metadata } from "next";

import ComingSoonView from "@/components/launch/ComingSoonView";

// Repete siteName/locale/type do layout raiz — Next.js substitui o objeto
// `openGraph` do pai por inteiro quando a página filha define o seu
// próprio (confirmado antes em app/e/[slug]/page.tsx), então esses três
// campos precisam estar aqui de novo ou desapareceriam do preview de
// link.
export const metadata: Metadata = {
  title: "MemoVerse — Lançamento em breve",
  description:
    "Um novo universo para transformar suas memórias em experiências inesquecíveis.",
  openGraph: {
    siteName: "MemoVerse",
    locale: "pt_BR",
    type: "website",
    title: "MemoVerse — Lançamento em breve",
    description:
      "Um novo universo para transformar suas memórias em experiências inesquecíveis.",
  },
};

// Alcançável de duas formas: diretamente (esta rota existe por si só) e
// via rewrite transparente de "/" feito por middleware.ts enquanto
// isBeforeLaunch() for true (ver lib/launch.ts) — nos dois casos o
// conteúdo é o mesmo. Depois do lançamento, o rewrite para de acontecer;
// esta rota continua existindo mas não é mais o que "/" serve.
export default function ComingSoonPage() {
  return <ComingSoonView />;
}
