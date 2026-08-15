"use client";

import FadeIn from "../animations/FadeIn";

type ExperienceCardProps = {
  title: string;
  recipient: string;
  status: string;
  createdAt: string;
};

export default function ExperienceCard({
  title,
  recipient,
  status,
  createdAt,
}: ExperienceCardProps) {
  return (
    <FadeIn>
      <div
        className="
          rounded-3xl
          border
          border-white/10
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
        <div className="flex items-center justify-between">

          <span className="rounded-full bg-yellow-400/20 px-3 py-1 text-xs font-semibold text-yellow-300">
            {status}
          </span>

          <span className="text-xs text-slate-400">
            {createdAt}
          </span>

        </div>

        <h2 className="mt-6 text-2xl font-bold text-white">
          {title}
        </h2>

        <p className="mt-3 text-slate-400">
          Para {recipient}
        </p>

      </div>
    </FadeIn>
  );
}