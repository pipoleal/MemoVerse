import type { CleanupPreviewReport } from "./useAdminDashboardData";

// Read-only de propósito: mostra as MESMAS contagens de candidatos que
// `python manage.py lifecycle_cleanup --dry-run` já reporta (ver
// apps.experiences.management.commands.lifecycle_cleanup) — nenhum botão
// de ação aqui. Etapa 9B — a exclusão automática continua fora de escopo
// até uma etapa de --apply ser explicitamente autorizada.
export default function LifecycleAlertsPanel({ cleanup }: { cleanup: CleanupPreviewReport }) {
  const rows = [
    { label: "Drafts abandonados (candidatos)", count: cleanup.candidates.draft_abandoned.count },
    { label: "Drafts payment_failed (candidatos)", count: cleanup.candidates.draft_payment_failed.count },
    { label: "Mídia pending travada (candidata)", count: cleanup.candidates.media_pending_stale.count },
    { label: "Mídia failed (candidata)", count: cleanup.candidates.media_failed_stale.count },
  ];
  const totalAlerts = rows.reduce((sum, row) => sum + row.count, 0);

  return (
    <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">Alertas de lifecycle</h2>
        <span className="text-xs text-slate-500">Nenhuma exclusão automática — só leitura</span>
      </div>

      {totalAlerts === 0 ? (
        <p className="mt-6 text-sm text-slate-400">Nenhum candidato de retenção encontrado agora.</p>
      ) : (
        <ul className="mt-6 flex flex-col gap-3">
          {rows
            .filter((row) => row.count > 0)
            .map((row) => (
              <li key={row.label} className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3">
                <span className="text-sm text-slate-300">{row.label}</span>
                <span className="rounded-full bg-yellow-400/15 px-3 py-1 text-sm font-bold text-yellow-300">
                  {row.count}
                </span>
              </li>
            ))}
        </ul>
      )}
    </section>
  );
}
