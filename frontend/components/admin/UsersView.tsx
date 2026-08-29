"use client";

import { useState } from "react";

import AdminPagination from "@/components/admin/AdminPagination";
import { useAdminPaginatedList } from "@/components/admin/useAdminPaginatedList";

// Forma de cada linha de GET /api/ops/9b4/users/ (ver apps.ops.views.
// UserListView) — nunca inclui password/hash. is_admin já vem calculado
// pelo backend via is_production_admin(), nunca recalculado aqui.
type AdminUserRow = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_superuser: boolean;
  is_admin: boolean;
  stars_count: number;
  created_at: string;
};

const LIMIT = 25;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function UsersView() {
  const [offset, setOffset] = useState(0);
  const { data, loading, error } = useAdminPaginatedList<AdminUserRow>("/ops/9b4/users/", LIMIT, offset);

  return (
    <div className="flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-black sm:text-3xl">Usuários</h1>
        <p className="mt-1 text-sm text-slate-400">
          Listagem somente leitura — nenhuma edição, suspensão ou exclusão de conta é feita por aqui.
        </p>
      </div>

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar os usuários agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando usuários…
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold sm:px-8">Nome</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">E-mail</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Status</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Estrelas</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Criado em</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.results.map((user) => (
                  <tr key={user.id} className="transition hover:bg-white/5">
                    <td className="px-6 py-4 font-semibold text-slate-200 sm:px-8">
                      {user.first_name} {user.last_name}
                    </td>
                    <td className="px-6 py-4 text-slate-400 sm:px-8">{user.email}</td>
                    <td className="px-6 py-4 sm:px-8">
                      <div className="flex flex-wrap gap-1.5">
                        {!user.is_active && (
                          <span className="rounded-full bg-red-400/15 px-2.5 py-1 text-xs font-bold text-red-300">
                            Inativo
                          </span>
                        )}
                        {user.is_admin && (
                          <span className="rounded-full bg-yellow-400/15 px-2.5 py-1 text-xs font-bold text-yellow-300">
                            Admin
                          </span>
                        )}
                        {user.is_active && !user.is_admin && (
                          <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-slate-300">
                            Ativo
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-400 sm:px-8">{user.stars_count}</td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{formatDate(user.created_at)}</td>
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
