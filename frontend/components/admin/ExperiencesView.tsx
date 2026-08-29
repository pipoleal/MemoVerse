"use client";

import Link from "next/link";
import { useState } from "react";

import AdminPagination from "@/components/admin/AdminPagination";
import { useAdminPaginatedList } from "@/components/admin/useAdminPaginatedList";
import { useDebouncedValue } from "@/components/admin/useDebouncedValue";

// Forma de cada linha de GET /api/ops/9b4/experiences/ (ver
// apps.ops.views.ExperienceListView) — só metadados operacionais, nunca
// title/letter/recipient_name/creator_name/short_message/context_answer
// nem qualquer URL de mídia (conteúdo privado do usuário) — isso só
// aparece no detalhe (/admin/experiences/[id]), sob clique explícito.
type AdminExperienceRow = {
  id: string;
  owner_email: string | null;
  status: "draft" | "awaiting_payment" | "payment_failed" | "paid" | "published";
  slug: string | null;
  experience_type: string;
  theme: string;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  expires_at: string | null;
};

const STATUS_LABELS: Record<AdminExperienceRow["status"], string> = {
  draft: "Rascunho",
  awaiting_payment: "Aguardando pagamento",
  payment_failed: "Pagamento falhou",
  paid: "Pago",
  published: "Publicado",
};

const LIMIT = 25;

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function ExperiencesView() {
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 400);

  const { data, loading, error } = useAdminPaginatedList<AdminExperienceRow>(
    "/ops/9b4/experiences/",
    LIMIT,
    offset,
    statusFilter || undefined,
    "owner_email",
    debouncedSearch
  );

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black sm:text-3xl">Experiências</h1>
          <p className="mt-1 text-sm text-slate-400">
            Clique numa linha para ver o conteúdo completo (moderação) — a listagem mostra só metadados.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
            placeholder="Buscar por e-mail do dono…"
            className="w-64 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 placeholder:text-slate-500 backdrop-blur-xl focus:border-yellow-400/40 focus:outline-none"
          />
          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setOffset(0);
            }}
            className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 backdrop-blur-xl"
          >
            <option value="">Todos os status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value} className="bg-slate-900">
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar as experiências agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando experiências…
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold sm:px-8">Dono</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Status</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Tipo / Tema</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Slug</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Atualizado em</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Expira em</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.results.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-10 text-center text-slate-500 sm:px-8">
                      Nenhuma experiência encontrada.
                    </td>
                  </tr>
                )}
                {data.results.map((exp) => (
                  <tr key={exp.id}>
                    <td colSpan={6} className="p-0">
                      <Link
                        href={`/admin/experiences/${exp.id}`}
                        className="grid grid-cols-[1fr_1fr_1fr_1fr_1fr_1fr] items-center px-6 py-4 transition hover:bg-white/5 sm:px-8"
                      >
                        <span className="text-slate-400">{exp.owner_email ?? "— (anônimo)"}</span>
                        <span>
                          <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-slate-300">
                            {STATUS_LABELS[exp.status]}
                          </span>
                        </span>
                        <span className="text-slate-400">
                          {exp.experience_type || "—"} {exp.theme ? `/ ${exp.theme}` : ""}
                        </span>
                        <span className="font-mono text-xs text-slate-500">{exp.slug ?? "—"}</span>
                        <span className="text-slate-500">{formatDate(exp.updated_at)}</span>
                        <span className="text-slate-500">{formatDate(exp.expires_at)}</span>
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <AdminPagination count={data.count} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
        </div>
      )}
    </div>
  );
}
