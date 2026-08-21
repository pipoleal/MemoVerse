// Mesmo visual das tiles de components/dashboard/JourneyStats.tsx —
// mantém a linguagem visual do produto no painel administrativo.
export default function StatCard({
  emoji,
  value,
  label,
  tone = "default",
}: {
  emoji: string;
  value: string | number;
  label: string;
  tone?: "default" | "warning";
}) {
  return (
    <div
      className={`rounded-3xl border p-6 backdrop-blur-xl transition-all duration-300 hover:-translate-y-1 sm:p-8 ${
        tone === "warning"
          ? "border-red-400/30 bg-red-400/5 hover:border-red-400/50"
          : "border-white/10 bg-white/5 hover:border-yellow-400/40 hover:shadow-[0_0_40px_rgba(250,204,21,.12)]"
      }`}
    >
      <div className="text-3xl sm:text-4xl">{emoji}</div>
      <h3 className="mt-4 text-3xl font-black text-white sm:mt-6 sm:text-4xl">{value}</h3>
      <p className="mt-2 text-sm text-slate-400 sm:text-base">{label}</p>
    </div>
  );
}
