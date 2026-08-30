"use client";

import { FormEvent, useEffect, useState } from "react";

import AdminConfirmDialog from "@/components/admin/AdminConfirmDialog";
import AdminPagination from "@/components/admin/AdminPagination";
import { useAdminPaginatedList } from "@/components/admin/useAdminPaginatedList";
import { useCreateDiscount } from "@/components/admin/useCreateDiscount";
import { useDebouncedValue } from "@/components/admin/useDebouncedValue";
import { useDeleteDiscount } from "@/components/admin/useDeleteDiscount";
import { fetchActivePlans, formatPlanPrice, type Plan } from "@/lib/checkout";

// Forma de cada linha de GET /api/ops/9b4/discounts/ (ver
// apps.ops.views.PlanDiscountListView).
type AdminDiscountRow = {
  id: string;
  email: string;
  plan_code: string;
  price: string;
  currency: string;
  note: string;
  is_active: boolean;
  created_by_email: string | null;
  redeemed_at: string | null;
  created_at: string;
};

const LIMIT = 25;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function DiscountsView() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 400);
  const [reloadToken, setReloadToken] = useState(0);
  const [pendingDelete, setPendingDelete] = useState<AdminDiscountRow | null>(null);
  const { deleteDiscount, loading: deleting, error: deleteError, clearError: clearDeleteError } =
    useDeleteDiscount();

  const { data, loading, error } = useAdminPaginatedList<AdminDiscountRow>(
    "/ops/9b4/discounts/",
    LIMIT,
    offset,
    undefined,
    "email",
    debouncedSearch,
    reloadToken
  );

  const [plans, setPlans] = useState<Plan[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetchActivePlans()
      .then((result) => {
        if (!cancelled) setPlans(result);
      })
      .catch(() => {
        if (!cancelled) setPlans([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const [email, setEmail] = useState("");
  const [planCode, setPlanCode] = useState("");
  const [price, setPrice] = useState("");
  const [note, setNote] = useState("");
  const { createDiscount, loading: creating, error: createError, clearError: clearCreateError } =
    useCreateDiscount();

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearCreateError();
    const ok = await createDiscount({ email, plan_code: planCode, price, note: note || undefined });
    if (ok) {
      setEmail("");
      setPlanCode("");
      setPrice("");
      setNote("");
      setOffset(0);
      setReloadToken((token) => token + 1);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const ok = await deleteDiscount(pendingDelete.id);
    if (ok) {
      setPendingDelete(null);
      setReloadToken((token) => token + 1);
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-black sm:text-3xl">Descontos</h1>
        <p className="mt-1 text-sm text-slate-400">
          Dê a um e-mail específico um preço combinado num plano — vale só na próxima compra desse e-mail
          nesse plano, e desativa sozinho depois de usado.
        </p>
      </div>

      <form
        onSubmit={handleCreate}
        className="flex flex-col gap-4 rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400">E-mail do amigo</label>
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="amigo@gmail.com"
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:border-yellow-400/40 focus:outline-none"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Plano</label>
            <select
              required
              value={planCode}
              onChange={(event) => setPlanCode(event.target.value)}
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-slate-200 focus:border-yellow-400/40 focus:outline-none"
            >
              <option value="" className="bg-slate-900">
                {plans === null ? "Carregando…" : "Selecione um plano"}
              </option>
              {plans?.map((plan) => (
                <option key={plan.code} value={plan.code} className="bg-slate-900">
                  {plan.name} ({formatPlanPrice(plan.price, plan.currency)})
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Preço combinado (R$)</label>
            <input
              required
              inputMode="decimal"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              placeholder="9.90"
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:border-yellow-400/40 focus:outline-none"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold text-slate-400">Nota (opcional)</label>
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="amigo do Instagram"
              className="rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-500 focus:border-yellow-400/40 focus:outline-none"
            />
          </div>
        </div>

        {createError && (
          <p className="rounded-xl border border-red-400/30 bg-red-400/5 p-3 text-sm text-red-200">
            {createError}
          </p>
        )}

        <div>
          <button
            type="submit"
            disabled={creating}
            className="rounded-full bg-yellow-400 px-5 py-2 text-sm font-semibold text-black transition hover:scale-105 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {creating ? "Criando…" : "Criar desconto"}
          </button>
        </div>
      </form>

      <div>
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
          Não foi possível carregar os descontos agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando descontos…
        </div>
      )}

      {data && (
        <div className="overflow-hidden rounded-3xl border border-white/10 bg-white/5 backdrop-blur-xl">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-left text-sm">
              <thead className="border-b border-white/10 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-6 py-4 font-semibold sm:px-8">E-mail</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Plano</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Preço</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Status</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Nota</th>
                  <th className="px-6 py-4 font-semibold sm:px-8">Criado em</th>
                  <th className="px-6 py-4 font-semibold sm:px-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {data.results.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-10 text-center text-slate-500 sm:px-8">
                      Nenhum desconto cadastrado.
                    </td>
                  </tr>
                )}
                {data.results.map((discount) => (
                  <tr key={discount.id} className="transition hover:bg-white/5">
                    <td className="px-6 py-4 text-slate-400 sm:px-8">{discount.email}</td>
                    <td className="px-6 py-4 text-slate-400 sm:px-8">{discount.plan_code}</td>
                    <td className="px-6 py-4 font-semibold text-slate-200 sm:px-8">
                      {formatPlanPrice(discount.price, discount.currency)}
                    </td>
                    <td className="px-6 py-4 sm:px-8">
                      {discount.is_active ? (
                        <span className="rounded-full bg-emerald-400/15 px-2.5 py-1 text-xs font-bold text-emerald-300">
                          Disponível
                        </span>
                      ) : (
                        <span className="rounded-full bg-white/10 px-2.5 py-1 text-xs font-semibold text-slate-400">
                          {discount.redeemed_at ? `Usado em ${formatDate(discount.redeemed_at)}` : "Inativo"}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{discount.note || "—"}</td>
                    <td className="px-6 py-4 text-slate-500 sm:px-8">{formatDate(discount.created_at)}</td>
                    <td className="px-6 py-4 text-right sm:px-8">
                      <button
                        type="button"
                        onClick={() => {
                          clearDeleteError();
                          setPendingDelete(discount);
                        }}
                        className="rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1.5 text-xs font-semibold text-red-300 transition hover:border-red-400/60 hover:text-red-200"
                      >
                        Apagar
                      </button>
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
          title="Apagar desconto"
          description={`Apaga o desconto de ${pendingDelete.email} no plano ${pendingDelete.plan_code}. Se ainda estiver disponível, o amigo deixa de poder usá-lo.`}
          confirmLabel="Apagar desconto"
          danger
          loading={deleting}
          errorMessage={deleteError}
          onConfirm={confirmDelete}
          onCancel={() => {
            setPendingDelete(null);
            clearDeleteError();
          }}
        />
      )}
    </div>
  );
}
