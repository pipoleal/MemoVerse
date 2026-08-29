export default function AdminPagination({
  count,
  limit,
  offset,
  onOffsetChange,
}: {
  count: number;
  limit: number;
  offset: number;
  onOffsetChange: (nextOffset: number) => void;
}) {
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(count / limit));

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 px-6 py-4 text-sm text-slate-400 sm:px-8">
      <span>
        {count} registro(s) — página {page} de {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 font-semibold text-slate-200 transition hover:border-yellow-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-white/15"
        >
          Anterior
        </button>
        <button
          type="button"
          disabled={offset + limit >= count}
          onClick={() => onOffsetChange(offset + limit)}
          className="rounded-full border border-white/15 bg-white/5 px-4 py-1.5 font-semibold text-slate-200 transition hover:border-yellow-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-white/15"
        >
          Próxima
        </button>
      </div>
    </div>
  );
}
