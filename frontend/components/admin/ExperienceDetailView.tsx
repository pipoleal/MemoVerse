"use client";

import Link from "next/link";

import { useExperienceDetail } from "@/components/admin/useExperienceDetail";

const STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  awaiting_payment: "Aguardando pagamento",
  payment_failed: "Pagamento falhou",
  paid: "Pago",
  published: "Publicado",
};

function Field({ label, value }: { label: string; value: string }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-200">{value}</p>
    </div>
  );
}

export default function ExperienceDetailView({ draftId }: { draftId: string }) {
  const { data, loading, error, notFound } = useExperienceDetail(draftId);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <Link href="/admin/experiences" className="text-xs font-semibold text-slate-500 hover:text-slate-300">
          ← Voltar para Experiências
        </Link>
        <h1 className="mt-3 text-2xl font-black sm:text-3xl">Detalhe da experiência</h1>
        <p className="mt-1 rounded-2xl border border-yellow-400/20 bg-yellow-400/5 px-4 py-2 text-sm text-yellow-200">
          Conteúdo privado do usuário, visível aqui só para moderação (denúncia/verificação de abuso). Este
          acesso fica registrado no log do backend.
        </p>
      </div>

      {notFound && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Experiência não encontrada.
        </div>
      )}

      {error && (
        <div className="rounded-3xl border border-red-400/30 bg-red-400/5 p-6 text-sm text-red-200">
          Não foi possível carregar esta experiência agora. Tente recarregar a página.
        </div>
      )}

      {!error && !notFound && (loading || !data) && (
        <div className="rounded-3xl border border-white/10 bg-white/5 p-10 text-center text-sm text-slate-400">
          Carregando…
        </div>
      )}

      {data && (
        <>
          <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-sm text-slate-400">{data.owner_email ?? "— (anônimo)"}</p>
                <p className="text-xs text-slate-500">
                  {data.experience_type || "—"} {data.theme ? `/ ${data.theme}` : ""}
                </p>
              </div>
              <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-slate-300">
                {STATUS_LABELS[data.status] ?? data.status}
              </span>
            </div>

            <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2">
              <Field label="Título" value={data.title} />
              <Field label="Destinatário" value={data.recipient_name} />
              <Field label="Criador(a)" value={data.creator_name} />
              <Field label="Data do evento" value={data.event_date ?? ""} />
              <Field label="Carta" value={data.letter} />
              <Field label="Mensagem curta" value={data.short_message} />
              <Field label="Resposta de contexto" value={data.context_answer} />
              <Field label="Slug público" value={data.slug ?? ""} />
            </div>
          </section>

          <section className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl sm:p-8">
            <h2 className="text-sm font-semibold uppercase tracking-[0.35em] text-yellow-400">
              Mídia ({data.media.length})
            </h2>

            {data.media.length === 0 ? (
              <p className="mt-4 text-sm text-slate-500">Nenhuma mídia nesta experiência.</p>
            ) : (
              <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {data.media.map((item) => (
                  <div key={item.id} className="overflow-hidden rounded-2xl border border-white/10 bg-black/30">
                    {item.url && item.media_type === "photo" && (
                      // eslint-disable-next-line @next/next/no-img-element -- URL assinada e temporária do R2, não passa pelo otimizador de imagens do Next.
                      <img src={item.url} alt={item.caption || "Mídia da experiência"} className="aspect-square w-full object-cover" />
                    )}
                    {item.url && item.media_type === "video" && (
                      <video src={item.url} controls className="aspect-square w-full object-cover" />
                    )}
                    {!item.url && (
                      <div className="flex aspect-square w-full items-center justify-center text-xs text-slate-500">
                        {item.upload_status === "pending" ? "Upload pendente" : "Upload falhou"}
                      </div>
                    )}
                    <div className="p-2 text-xs text-slate-400">{item.caption || "—"}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
