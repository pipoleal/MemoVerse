import type {
  CleanupCandidateGroup,
  CleanupNeverRemovedGroup,
  FullCleanupPreviewReport,
} from "./useLifecycleCleanupReport";

function CandidateRow({ label, group }: { label: string; group: CleanupCandidateGroup }) {
  return (
    <li className="rounded-2xl bg-white/5 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-300">{label}</span>
        <span
          className={`rounded-full px-3 py-1 text-sm font-bold ${
            group.count > 0 ? "bg-yellow-400/15 text-yellow-300" : "bg-white/10 text-slate-400"
          }`}
        >
          {group.count}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">{group.reason}</p>
      {group.sample_ids.length > 0 && (
        <p className="mt-2 truncate font-mono text-[11px] text-slate-600" title={group.sample_ids.join(", ")}>
          amostra: {group.sample_ids.slice(0, 5).join(", ")}
          {group.sample_ids.length > 5 ? "…" : ""}
        </p>
      )}
    </li>
  );
}

function NeverRemovedRow({ label, group }: { label: string; group: CleanupNeverRemovedGroup }) {
  return (
    <li className="rounded-2xl bg-white/5 px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-slate-300">{label}</span>
        <span className="rounded-full bg-white/10 px-3 py-1 text-sm font-bold text-slate-300">{group.count}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">{group.reason}</p>
    </li>
  );
}

// Read-only, de propósito: os mesmos candidatos que `lifecycle_cleanup
// --dry-run` já reporta. Nenhum botão de exclusão/aplicação aqui — a
// política de retenção existe só como preview até uma etapa de aplicação
// real ser explicitamente autorizada em separado (ver docstring do
// management command).
export default function LifecycleCleanupDetail({ report }: { report: FullCleanupPreviewReport }) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">
          Candidatos de retenção
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Nunca removidos automaticamente por esta ferramenta — apenas classificados sob a política atual.
        </p>
        <ul className="mt-6 flex flex-col gap-3">
          <CandidateRow label="Drafts abandonados" group={report.candidates.draft_abandoned} />
          <CandidateRow label="Drafts anônimos não reivindicados" group={report.candidates.draft_anonymous_unclaimed} />
          <CandidateRow label="Drafts com pagamento falho" group={report.candidates.draft_payment_failed} />
          <CandidateRow label="Mídia pendente parada" group={report.candidates.media_pending_stale} />
          <CandidateRow label="Mídia com falha" group={report.candidates.media_failed_stale} />
        </ul>
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">
          Nunca removidos automaticamente
        </h2>
        <p className="mt-1 text-xs text-slate-500">Regra de negócio — apenas inventário/alerta para investigação manual.</p>
        <ul className="mt-6 flex flex-col gap-3">
          <NeverRemovedRow label="Drafts pagos ainda não publicados" group={report.never_removed.draft_paid_unpublished} />
          <NeverRemovedRow label="Publicados expirados" group={report.never_removed.draft_published_expired} />
          <NeverRemovedRow label="Pagamentos em status terminal" group={report.never_removed.payment_financial_terminal} />
          <NeverRemovedRow
            label="Pagamento ativo com draft inconsistente"
            group={report.never_removed.payment_invariant_inconsistent}
          />
          <NeverRemovedRow label="Eventos de webhook (sem política definida)" group={report.never_removed.webhook_events} />
        </ul>
      </section>
    </div>
  );
}
