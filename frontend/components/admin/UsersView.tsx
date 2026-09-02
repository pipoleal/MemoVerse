"use client";

import { useState } from "react";

import AdminConfirmDialog from "@/components/admin/AdminConfirmDialog";
import AdminPagination from "@/components/admin/AdminPagination";
import { useAdminPaginatedList } from "@/components/admin/useAdminPaginatedList";
import { useDebouncedValue } from "@/components/admin/useDebouncedValue";
import { useDeleteUser } from "@/components/admin/useDeleteUser";

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

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function UsersView() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 400);
  const [reloadToken, setReloadToken] = useState(0);
  const [pendingDelete, setPendingDelete] = useState<AdminUserRow | null>(null);
  const { deleteUser, loading: deleting, error: deleteError, clearError } = useDeleteUser();

  const { data, loading, error } = useAdminPaginatedList<AdminUserRow>(
    "/ops/9b4/users/",
    LIMIT,
    offset,
    undefined,
    "email",
    debouncedSearch,
    reloadToken
  );

  async function confirmDelete() {
    if (!pendingDelete) return;
    const ok = await deleteUser(pendingDelete.id);
    if (ok) {
      setPendingDelete(null);
      setReloadToken((token) => token + 1);
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black sm:text-3xl">Usuários</h1>
          <p className="mt-1 text-sm text-slate-400">
            Excluir uma conta só é permitido quando ela não tem nenhum histórico de pagamento.
          </p>
        </div>

        <input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setOffset(0);
          }}
          placeholder="Buscar por e-mail…"
          className="w-64 rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 placeholder:text-slate-500 backdrop-blur-xl focus:border-yellow-400/40 focus:outline-none"
        />
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
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold sm:px-8">Nome</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">E-mail</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Status</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Estrelas</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Criado em</th>
                  <th className="px-6 py-4 font-semibold sm:px-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.results.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-6 py-10 text-center text-slate-500 sm:px-8">
                      Nenhum usuário encontrado.
                    </td>
                  </tr>
                )}
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
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{formatDateTime(user.created_at)}</td>
                    <td className="px-6 py-4 text-right sm:px-8">
                      {!user.is_admin && (
                        <button
                          type="button"
                          onClick={() => {
                            clearError();
                            setPendingDelete(user);
                          }}
                          className="rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1.5 text-xs font-semibold text-red-300 transition hover:border-red-400/60 hover:text-red-200"
                        >
                          Excluir
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <AdminPagination count={data.count} limit={data.limit} offset={data.offset} onOffsetChange={setOffset} />
        </div>
      )}

      {pendingDelete && (
        <AdminConfirmDialog
          title="Excluir usuário"
          description={`Isso apaga permanentemente a conta de ${pendingDelete.email} e todas as experiências dela ainda em rascunho (sem publicação, sem pagamento). Contas com histórico de pagamento são bloqueadas automaticamente.`}
          confirmLabel="Excluir permanentemente"
          requireText={pendingDelete.email}
          danger
          loading={deleting}
          errorMessage={deleteError}
          onConfirm={confirmDelete}
          onCancel={() => {
            setPendingDelete(null);
            clearError();
          }}
        />
      )}
    </div>
  );
}
