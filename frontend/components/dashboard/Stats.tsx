"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import FadeIn from "../animations/FadeIn";

type Media = {
  media_type: "photo" | "video";
  upload_status: "pending" | "uploaded" | "failed";
};

type Draft = {
  id: string;
  media: Media[];
};

function countUploaded(drafts: Draft[], mediaType: Media["media_type"]) {
  return drafts.reduce(
    (total, draft) =>
      total + draft.media.filter((item) => item.media_type === mediaType && item.upload_status === "uploaded").length,
    0
  );
}

export default function Stats() {
  const [drafts, setDrafts] = useState<Draft[] | null>(null);

  useEffect(() => {
    let cancelled = false;

    api
      .get<Draft[]>("/experiences/drafts/")
      .then((response) => {
        if (!cancelled) setDrafts(response.data);
      })
      .catch(() => {
        if (!cancelled) setDrafts(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const stats = [
    {
      emoji: "⭐",
      value: drafts === null ? "—" : String(drafts.length),
      label: "Experiências",
    },
    {
      emoji: "📸",
      value: drafts === null ? "—" : String(countUploaded(drafts, "photo")),
      label: "Fotos",
    },
    {
      emoji: "🎬",
      value: drafts === null ? "—" : String(countUploaded(drafts, "video")),
      label: "Vídeos",
    },
  ];

  return (
    <FadeIn delay={0.8}>
      <section className="mt-14 grid gap-6 md:grid-cols-3">
        {stats.map((item) => (
          <div
            key={item.label}
            className="
              rounded-3xl
              border border-white/10
              bg-white/5
              p-8
              backdrop-blur-xl
              transition-all
              duration-300
              hover:-translate-y-2
              hover:border-yellow-400/40
              hover:shadow-[0_0_40px_rgba(250,204,21,.15)]
            "
          >
            <div className="text-4xl">
              {item.emoji}
            </div>

            <h2 className="mt-6 text-5xl font-black text-white">
              {item.value}
            </h2>

            <p className="mt-2 text-slate-400">
              {item.label}
            </p>
          </div>
        ))}
      </section>
    </FadeIn>
  );
}