"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import ExperienceCard from "./ExperienceCard";
import FadeIn from "../animations/FadeIn";

type Draft = {
  id: string;
  status: string;
  slug: string | null;
  title: string;
  recipient_name: string;
  created_at: string;
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  awaiting_payment: "Aguardando pagamento",
  payment_failed: "Pagamento falhou",
  paid: "Pago",
  published: "Publicado",
};

function formatCreatedAt(createdAt: string) {
  const date = new Date(createdAt);

  if (Number.isNaN(date.getTime())) {
    return createdAt;
  }

  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export default function ExperienceList() {
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    api
      .get<Draft[]>("/experiences/drafts/")
      .then((response) => {
        if (!cancelled) setDrafts(response.data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <p className="text-slate-400">
        Não foi possível carregar suas experiências agora.
      </p>
    );
  }

  if (drafts === null) {
    return <p className="text-slate-400">Carregando experiências...</p>;
  }

  if (drafts.length === 0) {
    return (
      <FadeIn>
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center backdrop-blur-xl">
          <p className="text-slate-300">
            Você ainda não criou nenhuma experiência.
          </p>
        </div>
      </FadeIn>
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {drafts.map((draft) => (
        <ExperienceCard
          key={draft.id}
          id={draft.id}
          slug={draft.slug}
          title={draft.title || "Sem título"}
          recipient={draft.recipient_name || "—"}
          status={draft.status}
          statusLabel={STATUS_LABELS[draft.status] ?? draft.status}
          createdAt={formatCreatedAt(draft.created_at)}
        />
      ))}
    </div>
  );
}
