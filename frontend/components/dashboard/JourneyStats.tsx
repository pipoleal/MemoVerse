"use client";

import FadeIn from "../animations/FadeIn";
import type { Draft } from "./useDashboardData";

type JourneyStatsProps = {
  drafts: Draft[] | null;
  loading: boolean;
  error: boolean;
};

function formatEventDate(dateStr: string) {
  // event_date is a plain Django DateField ("YYYY-MM-DD") — parsed as local
  // (not UTC) by appending a time, so "today" comparisons below never shift
  // a day off because of timezone conversion.
  const date = new Date(`${dateStr}T00:00:00`);
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "long" }).format(date);
}

function nextUpcomingEventDate(drafts: Draft[]): string | null {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);

  const upcoming = drafts
    .filter((draft): draft is Draft & { event_date: string } => Boolean(draft.event_date))
    .map((draft) => ({ raw: draft.event_date, date: new Date(`${draft.event_date}T00:00:00`) }))
    .filter((item) => item.date.getTime() >= startOfToday.getTime())
    .sort((a, b) => a.date.getTime() - b.date.getTime());

  return upcoming[0]?.raw ?? null;
}

export default function JourneyStats({ drafts, loading, error }: JourneyStatsProps) {
  // Error is already surfaced once by ExperienceSection right below this —
  // no need to duplicate the same message in two places on the same page.
  if (error) return null;

  const total = drafts?.length ?? null;
  const published = drafts?.filter((draft) => draft.status === "published").length ?? null;
  const inProgress = drafts && total !== null && published !== null ? total - published : null;
  const nextEventDate = drafts ? nextUpcomingEventDate(drafts) : null;

  const stats = [
    { emoji: "✦", value: loading ? "—" : String(total), label: "Experiências criadas" },
    { emoji: "⭐", value: loading ? "—" : String(published), label: "Memórias eternizadas" },
    { emoji: "📝", value: loading ? "—" : String(inProgress), label: "Em andamento" },
  ];

  // Only shown when a real future date exists — never a placeholder "—"
  // card for a metric that simply has no data yet.
  if (!loading && nextEventDate) {
    stats.push({ emoji: "📅", value: formatEventDate(nextEventDate), label: "Próxima data especial" });
  }

  return (
    <FadeIn delay={0.4}>
      <section>
        <h2 className="mb-6 text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">Sua jornada</h2>

        <div className="grid grid-cols-2 gap-4 sm:gap-6 lg:grid-cols-4">
          {stats.map((item) => (
            <div
              key={item.label}
              className="
                rounded-3xl border border-white/10 bg-white/5 p-6
                backdrop-blur-xl transition-all duration-300
                hover:-translate-y-1 hover:border-yellow-400/40
                hover:shadow-[0_0_40px_rgba(250,204,21,.12)]
                sm:p-8
              "
            >
              <div className="text-3xl sm:text-4xl">{item.emoji}</div>

              <h3 className="mt-4 text-3xl font-black text-white sm:mt-6 sm:text-4xl">{item.value}</h3>

              <p className="mt-2 text-sm text-slate-400 sm:text-base">{item.label}</p>
            </div>
          ))}
        </div>
      </section>
    </FadeIn>
  );
}
