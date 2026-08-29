"use client";

import { useSettingsSnapshot } from "@/components/admin/useSettingsSnapshot";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex items-center justify-between gap-4 rounded-2xl bg-white/5 px-4 py-3">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="text-right text-sm font-semibold text-slate-200">{value}</span>
    </li>
  );
}

export default function SettingsView() {
  const { data, loading, error } = useSettingsSnapshot();

  return (
    <div className="flex flex-col gap-10">
      <div>
        <h1 className="text-2xl font-black sm:text-3xl">Configurações</h1>
        <p className="mt-1 text-sm text-slate-400">
          Snapshot somente leitura das flags operacionais do backend — nenhum segredo, token ou chave aparece
          aqui.
        </p>
      </div>

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar as configurações agora. Tente recarregar a página.
        </div>
      )}

      {!error && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando configurações…
        </div>
      )}

      {data && (
        <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
          <ul className="flex flex-col gap-3">
            <Row label="Ambiente" value={data.debug ? "Debug (desenvolvimento)" : "Produção"} />
            <Row label="Ambiente Mercado Pago" value={data.mercado_pago_environment} />
            <Row label="Cloudflare R2" value={data.r2_configured ? `Configurado (${data.r2_bucket_name})` : "Não configurado"} />
            <Row label="Backend de e-mail" value={data.email_backend} />
            <Row
              label="Expiração de mídia pendente"
              value={`${data.pending_media_expiration_minutes} min`}
            />
            <Row
              label="E-mail admin configurado"
              value={data.memoverse_admin_email ?? "Não configurado"}
            />
            <Row label="Hosts permitidos" value={data.allowed_hosts.join(", ") || "—"} />
          </ul>
        </section>
      )}
    </div>
  );
}
