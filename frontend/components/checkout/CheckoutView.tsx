"use client";

import { useEffect, useRef, useState } from "react";

import CardPaymentBlock from "./CardPaymentBlock";
import ThemeVisual from "@/components/dashboard/ThemeVisual";
import {
  createOrResumeCheckout,
  displayPlanHighlight,
  displayPlanName,
  extractCheckoutErrorMessage,
  fetchActivePlans,
  fetchDraftPaymentStatus,
  formatPlanPrice,
  getActiveConflictPlanCode,
  planCardTitle,
  FAILED_PAYMENT_STATUSES,
  type CardCheckoutData,
  type CheckoutResponse,
  type PaymentMethodChoice,
  type PaymentStatus,
  type Plan,
} from "@/lib/checkout";
import { extractPublishErrorMessage, publishDraft } from "@/lib/publish";
import { fetchPublicExperience } from "@/lib/publicExperience";

const POLL_INTERVAL_MS = 5000;

type Phase =
  | { kind: "loading" }
  // No payment exists yet for this draft: the user must actively choose a
  // plan (fetched from GET /payments/plans/ — never hardcoded) before
  // anything else can happen.
  | { kind: "selecting_plan"; plans: Plan[] }
  // Plan chosen, but no Payment/Order created yet — still needs Pix or
  // Cartão before startCheckout is ever called (only ever called from here
  // after an explicit choice).
  | { kind: "selecting_method"; plan: Plan }
  | { kind: "creating"; method: PaymentMethodChoice }
  | { kind: "awaiting_payment"; checkout: CheckoutResponse; method: PaymentMethodChoice }
  | { kind: "approved"; checkout: CheckoutResponse | null }
  // planCode always carried separately from checkout (which can be null —
  // e.g. an already-expired Pix discovered on page load, before any local
  // checkout call happened this session) so a retry can always resolve the
  // plan to offer again, even without a full Plan object in hand.
  | { kind: "payment_failed"; status: PaymentStatus; checkout: CheckoutResponse | null; planCode: string }
  | { kind: "error"; message: string };

// displayPlanName/displayPlanHighlight/planCardTitle agora vivem em
// @/lib/checkout — a landing page (PricingPreview.tsx) precisa exatamente
// da mesma transformação de apresentação, e frontend/CLAUDE.md pede para
// nunca duplicar lógica existente entre componentes.

// Reused wherever the currently-selected/checked-out plan needs to be
// summarized — never re-derived or hardcoded a second time.
function currentPlanForSummary(phase: Phase): Plan | null {
  if (phase.kind === "selecting_method") return phase.plan;
  if ("checkout" in phase && phase.checkout) return phase.checkout.plan;
  return null;
}

function statusLabel(status: PaymentStatus): string {
  switch (status) {
    case "pending":
      return "Aguardando pagamento";
    case "in_process":
      return "Processando pagamento";
    case "action_required":
      return "Aguardando pagamento";
    case "rejected":
      return "Pagamento recusado";
    case "cancelled":
      return "Pagamento cancelado";
    case "expired":
      return "Pix expirado";
    case "refunded":
      return "Pagamento reembolsado";
    case "approved":
      return "Pagamento aprovado";
    default:
      return status;
  }
}

export default function CheckoutView({ draftId }: { draftId: string }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [copyFeedback, setCopyFeedback] = useState<"idle" | "copied" | "failed">("idle");
  // Cache of the last fetched plan catalog, kept in sync wherever
  // fetchActivePlans() is called (initialize, retryAfterFailure) — lets
  // "Voltar aos planos" return to selecting_plan instantly, as a pure local
  // state transition, without ever re-fetching or touching the backend.
  const [plans, setPlans] = useState<Plan[]>([]);

  // Guards the initial mount sequence against React StrictMode's dev-only
  // double-invoke of effects — without this, two POST/GET requests would
  // fire for a single real page load.
  const hasInitializedRef = useRef(false);

  async function startCheckout(
    planCode: string,
    method: PaymentMethodChoice,
    cardData?: CardCheckoutData,
    isRetryAfterConflict = false
  ) {
    setPhase({ kind: "creating", method });

    try {
      const result = await createOrResumeCheckout(draftId, planCode, method, cardData);
      applyCheckoutResult(result, method);
    } catch (error) {
      const conflictPlanCode = !isRetryAfterConflict ? getActiveConflictPlanCode(error) : null;

      if (conflictPlanCode) {
        // A different plan_code already has an active checkout for this
        // draft. Recoverable: resume that one instead of failing outright.
        await startCheckout(conflictPlanCode, method, cardData, true);
        return;
      }

      // Card tokens are single-use: on failure the user must go back through
      // the Brick for a fresh token rather than the page silently retrying
      // with the same (now-dead) token, so this always surfaces as an error
      // (never a silent retry) for both methods, same as before this change.
      setPhase({ kind: "error", message: extractCheckoutErrorMessage(error) });
    }
  }

  function applyCheckoutResult(result: CheckoutResponse, method: PaymentMethodChoice) {
    // The HTTP call succeeding is never treated as "paid" by itself — only
    // result.status (ultimately sourced from the Mercado Pago Order/webhook
    // confirmation) decides which phase this becomes.
    if (result.status === "approved") {
      setPhase({ kind: "approved", checkout: result });
    } else if (FAILED_PAYMENT_STATUSES.includes(result.status)) {
      setPhase({ kind: "payment_failed", status: result.status, checkout: result, planCode: result.plan.code });
    } else {
      setPhase({ kind: "awaiting_payment", checkout: result, method });
    }
  }

  // "Tentar novamente" after a failure never assumes the previously chosen
  // plan is still active (rare, but the catalog can change) — always
  // re-resolves it from the current catalog, falling back to full plan
  // selection if it's gone.
  async function retryAfterFailure(planCode: string) {
    setPhase({ kind: "loading" });
    try {
      const freshPlans = await fetchActivePlans();
      setPlans(freshPlans);
      if (freshPlans.length === 0) {
        setPhase({ kind: "error", message: "Nenhum plano disponível no momento. Tente novamente em instantes." });
        return;
      }
      const plan = freshPlans.find((candidate) => candidate.code === planCode);
      setPhase(plan ? { kind: "selecting_method", plan } : { kind: "selecting_plan", plans: freshPlans });
    } catch (error) {
      setPhase({ kind: "error", message: extractCheckoutErrorMessage(error) });
    }
  }

  async function initialize() {
    setPhase({ kind: "loading" });

    try {
      const data = await fetchDraftPaymentStatus(draftId);

      if (!data.payment) {
        // Nothing started yet: needs the real plan catalog before the user
        // can choose anything — only fetched here, never when resuming an
        // already-chosen plan below (that path doesn't need it).
        let fetchedPlans: Plan[];
        try {
          fetchedPlans = await fetchActivePlans();
        } catch (error) {
          setPhase({ kind: "error", message: extractCheckoutErrorMessage(error) });
          return;
        }
        setPlans(fetchedPlans);
        if (fetchedPlans.length === 0) {
          setPhase({ kind: "error", message: "Nenhum plano disponível no momento. Tente novamente em instantes." });
          return;
        }
        setPhase({ kind: "selecting_plan", plans: fetchedPlans });
        return;
      }

      if (data.payment.status === "approved") {
        setPhase({ kind: "approved", checkout: null });
        return;
      }

      if (FAILED_PAYMENT_STATUSES.includes(data.payment.status)) {
        setPhase({
          kind: "payment_failed",
          status: data.payment.status,
          checkout: null,
          planCode: data.payment.plan.code,
        });
        return;
      }

      // Active payment: resume it (fetches the QR/Pix or card-status
      // artifacts, which this status endpoint never returns) using the plan
      // already in use. Always resumed as "pix" here: when the Order was
      // already created (the overwhelmingly common case — Pix and card
      // Orders both get created synchronously during the original request),
      // start_checkout's mp_order_id short-circuit returns the existing
      // Payment as-is and this method argument is never actually used by the
      // backend. It only matters for the rare case of a previous attempt
      // that failed before the Order was ever created — a card attempt in
      // that exact narrow window can't be resumed automatically anyway
      // (its token was single-use and is already gone), so defaulting to
      // "pix" here carries forward the same limitation the checkout already
      // had before card payments existed (this endpoint's only method).
      await startCheckout(data.payment.plan.code, "pix");
    } catch (error) {
      setPhase({ kind: "error", message: extractCheckoutErrorMessage(error) });
    }
  }

  useEffect(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;
    void initialize();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId]);

  // Single polling timer, only while awaiting_payment. Stops on unmount, on
  // any phase change, or as soon as a terminal status is observed.
  useEffect(() => {
    if (phase.kind !== "awaiting_payment") return;

    let cancelled = false;

    const intervalId = setInterval(async () => {
      try {
        const data = await fetchDraftPaymentStatus(draftId);
        if (cancelled) return;

        const paymentStatus = data.payment?.status;
        if (!paymentStatus) return;

        if (paymentStatus === "approved") {
          setPhase((current) =>
            current.kind === "awaiting_payment" ? { kind: "approved", checkout: current.checkout } : current
          );
        } else if (FAILED_PAYMENT_STATUSES.includes(paymentStatus)) {
          setPhase((current) =>
            current.kind === "awaiting_payment"
              ? {
                  kind: "payment_failed",
                  status: paymentStatus,
                  checkout: current.checkout,
                  planCode: current.checkout.plan.code,
                }
              : current
          );
        }
        // Still pending/in_process/action_required: keep polling, nothing to update.
      } catch {
        // Transient network error while polling — try again next tick
        // instead of surfacing a scary error over a perfectly fine checkout.
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [phase.kind, draftId]);

  async function copyPixCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setCopyFeedback("copied");
    } catch {
      setCopyFeedback("failed");
    } finally {
      setTimeout(() => setCopyFeedback("idle"), 2500);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center bg-slate-950 px-4 py-10 text-white sm:px-6">
      <div className="w-full max-w-md">
        <p className="text-center text-sm font-semibold uppercase tracking-[0.3em] text-yellow-400">
          MemoVerse
        </p>
        <h1 className="mt-3 text-center text-3xl font-black">Finalizar pagamento</h1>

        {phase.kind !== "error" && phase.kind !== "loading" && phase.kind !== "selecting_plan" && (
          <div className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
            <PlanSummaryBlock plan={currentPlanForSummary(phase)} />
          </div>
        )}

        <div className="mt-6">
          {phase.kind === "loading" && <LoadingBlock message="Carregando pagamento..." />}

          {phase.kind === "selecting_plan" && (
            <PlanSelectionBlock plans={phase.plans} onSelect={(plan) => setPhase({ kind: "selecting_method", plan })} />
          )}

          {phase.kind === "selecting_method" && (
            <MethodSelectionBlock
              plan={phase.plan}
              onBack={() => setPhase({ kind: "selecting_plan", plans })}
              onChoosePix={() => void startCheckout(phase.plan.code, "pix")}
              onSubmitCard={(cardData) => startCheckout(phase.plan.code, "card", cardData)}
            />
          )}

          {phase.kind === "creating" && (
            <LoadingBlock
              message={phase.method === "card" ? "Processando pagamento..." : "Gerando seu Pix..."}
            />
          )}

          {phase.kind === "awaiting_payment" && phase.method === "pix" && (
            <AwaitingPaymentBlock
              checkout={phase.checkout}
              copyFeedback={copyFeedback}
              onCopy={copyPixCode}
            />
          )}

          {phase.kind === "awaiting_payment" && phase.method === "card" && (
            <CardProcessingBlock status={phase.checkout.status} />
          )}

          {phase.kind === "approved" && <ApprovedBlock draftId={draftId} />}

          {phase.kind === "payment_failed" && (
            <FailedBlock
              status={phase.status}
              onRetry={() => void retryAfterFailure(phase.planCode)}
            />
          )}

          {phase.kind === "error" && (
            <ErrorBlock message={phase.message} onRetry={() => void initialize()} />
          )}
        </div>
      </div>
    </main>
  );
}

function PlanSummaryBlock({ plan }: { plan: Plan | null }) {
  if (!plan) {
    return (
      <div>
        <p className="text-sm uppercase tracking-widest text-slate-400">Plano</p>
        <p className="mt-1 text-xl font-bold text-white">MemoVerse</p>
      </div>
    );
  }

  return (
    <div>
      <p className="text-sm uppercase tracking-widest text-slate-400">Plano</p>
      <p className="mt-1 text-xl font-bold text-white">{displayPlanName(plan.name)}</p>
      <p className="mt-4 text-sm uppercase tracking-widest text-slate-400">Total</p>
      <p className="text-2xl font-bold text-yellow-400">{formatPlanPrice(plan.price, plan.currency)}</p>
    </div>
  );
}

function PlanSelectionBlock({ plans, onSelect }: { plans: Plan[]; onSelect: (plan: Plan) => void }) {
  return (
    <div className="flex flex-col gap-4">
      {plans.map((plan) => (
        <PlanCard key={plan.code} plan={plan} onSelect={() => onSelect(plan)} />
      ))}
    </div>
  );
}

function PlanCard({ plan, onSelect }: { plan: Plan; onSelect: () => void }) {
  const isGalaxy = plan.features.galaxy_live_enabled;

  return (
    <div
      className={`flex flex-col items-center gap-3 rounded-3xl border p-6 text-center backdrop-blur-xl transition-all duration-300 ${
        isGalaxy
          ? "border-yellow-400/40 bg-linear-to-br from-yellow-400/10 via-white/5 to-purple-500/10 hover:border-yellow-400/60 hover:shadow-[0_0_50px_rgba(250,204,21,.18)]"
          : "border-white/10 bg-white/5 hover:border-yellow-400/30"
      }`}
    >
      {isGalaxy && (
        <span className="rounded-full bg-yellow-400/15 px-3 py-1 text-xs font-bold tracking-wide text-yellow-300">
          ✨ PREMIUM
        </span>
      )}
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">{planCardTitle(plan.name)}</p>
      <p className="text-3xl font-black text-white">{formatPlanPrice(plan.price, plan.currency)}</p>
      <ul className="w-full space-y-1.5 text-left text-sm text-slate-300">
        {plan.features.highlights.map((item) => (
          <li key={item} className="flex items-start gap-2">
            <span className="mt-0.5 text-yellow-400">✓</span>
            {displayPlanHighlight(item)}
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={onSelect}
        className="mt-2 w-full rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-[1.02] active:scale-95"
      >
        Escolher
      </button>
    </div>
  );
}

function MethodSelectionBlock({
  plan,
  onBack,
  onChoosePix,
  onSubmitCard,
}: {
  plan: Plan;
  onBack: () => void;
  onChoosePix: () => void;
  onSubmitCard: (cardData: CardCheckoutData) => Promise<void>;
}) {
  const [tab, setTab] = useState<PaymentMethodChoice>("pix");

  return (
    <div className="flex flex-col gap-6">
      <button
        type="button"
        onClick={onBack}
        className="self-start text-sm font-semibold text-slate-400 transition-colors hover:text-yellow-400"
      >
        ← Voltar aos planos
      </button>

      <div className="flex gap-2 rounded-full border border-white/10 bg-white/5 p-1">
        <button
          type="button"
          onClick={() => setTab("pix")}
          className={`flex-1 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
            tab === "pix" ? "bg-yellow-400 text-black" : "text-slate-300 hover:bg-white/10"
          }`}
        >
          Pix
        </button>
        <button
          type="button"
          onClick={() => setTab("card")}
          className={`flex-1 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
            tab === "card" ? "bg-yellow-400 text-black" : "text-slate-300 hover:bg-white/10"
          }`}
        >
          Cartão
        </button>
      </div>

      {tab === "pix" && (
        <div className="flex flex-col items-center gap-4 rounded-3xl border border-white/10 bg-white/5 p-8 text-center backdrop-blur-xl">
          <p className="text-slate-300">Pague com Pix e receba a confirmação em instantes.</p>
          <button
            type="button"
            onClick={onChoosePix}
            className="w-full rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-[1.02] active:scale-95"
          >
            Gerar Pix
          </button>
        </div>
      )}

      {tab === "card" && (
        <CardPaymentBlock amount={Number(plan.price)} onSubmit={onSubmitCard} />
      )}
    </div>
  );
}

function CardProcessingBlock({ status }: { status: PaymentStatus }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-3xl border border-white/10 bg-white/5 p-10 text-center backdrop-blur-xl">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
      <p className="text-slate-300">{statusLabel(status)}</p>
      <p className="text-sm text-slate-400">
        Assim que o pagamento for confirmado, esta página atualiza automaticamente.
      </p>
    </div>
  );
}

function LoadingBlock({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-3xl border border-white/10 bg-white/5 p-10 text-center backdrop-blur-xl">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
      <p className="text-slate-300">{message}</p>
    </div>
  );
}

function AwaitingPaymentBlock({
  checkout,
  copyFeedback,
  onCopy,
}: {
  checkout: CheckoutResponse;
  copyFeedback: "idle" | "copied" | "failed";
  onCopy: (code: string) => void;
}) {
  const { qr_code, qr_code_base64, ticket_url } = checkout.checkout;
  const hasAnyArtifact = Boolean(qr_code || qr_code_base64 || ticket_url);

  return (
    <div className="flex flex-col gap-6 rounded-3xl border border-white/10 bg-white/5 p-6 text-center backdrop-blur-xl">
      <div>
        <span className="inline-flex items-center gap-2 rounded-full bg-yellow-400/10 px-4 py-2 text-sm font-semibold text-yellow-300">
          <span className="h-2 w-2 animate-pulse rounded-full bg-yellow-400" />
          {statusLabel(checkout.status)}
        </span>
      </div>

      {qr_code_base64 && (
        <div className="mx-auto w-full max-w-65 rounded-2xl bg-white p-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:image/png;base64,${qr_code_base64}`}
            alt="QR Code do Pix"
            className="h-auto w-full"
          />
        </div>
      )}

      {qr_code && (
        <div className="text-left">
          <p className="mb-2 text-sm font-semibold text-slate-300">Pix copia e cola</p>
          <div className="max-h-28 overflow-y-auto break-all rounded-2xl border border-white/10 bg-black/30 p-4 text-xs text-slate-300">
            {qr_code}
          </div>
          <button
            type="button"
            onClick={() => onCopy(qr_code)}
            className="mt-3 w-full rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-[1.02] active:scale-95"
          >
            {copyFeedback === "copied" ? "✓ Código copiado" : "Copiar código Pix"}
          </button>
          {copyFeedback === "failed" && (
            <p className="mt-2 text-xs text-red-300">
              Não foi possível copiar automaticamente. Selecione o código acima manualmente.
            </p>
          )}
        </div>
      )}

      {ticket_url && (
        <a
          href={ticket_url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full rounded-full border border-white/20 px-6 py-3 font-semibold text-white transition-colors hover:bg-white/10"
        >
          Abrir comprovante Pix
        </a>
      )}

      {!hasAnyArtifact && (
        <p className="text-sm text-slate-400">
          O checkout foi criado, mas o Pix ainda não está pronto para exibição. Isso deve se resolver em
          instantes — a página vai atualizar sozinha assim que o pagamento for confirmado.
        </p>
      )}

      <p className="text-sm text-slate-400">
        Assim que o pagamento for confirmado, esta página atualiza automaticamente.
      </p>
    </div>
  );
}

type PublishPhase =
  | { kind: "idle" }
  | { kind: "publishing" }
  // title/theme são só cosméticos (preview temático + nome na tela de
  // sucesso) — vêm de uma segunda chamada best-effort depois do publish
  // (ver handlePublish); ficam "" quando essa chamada falha, e a tela de
  // sucesso renderiza normalmente sem esses dois detalhes.
  | { kind: "published"; slug: string; title: string; theme: string }
  | { kind: "error"; message: string };

function ApprovedBlock({ draftId }: { draftId: string }) {
  const [publishPhase, setPublishPhase] = useState<PublishPhase>({ kind: "idle" });

  async function handlePublish() {
    // Guards against a double click firing two requests — once published,
    // this branch is also never reachable again since the button is
    // replaced by the success screen below.
    if (publishPhase.kind === "publishing" || publishPhase.kind === "published") return;

    setPublishPhase({ kind: "publishing" });

    try {
      // draftId is exactly the one this whole page was loaded with (passed
      // straight through from CheckoutView, itself the /checkout/[draftId]
      // route param) — never re-derived or guessed here.
      const result = await publishDraft(draftId);

      // Best-effort: busca título/tema pela mesma rota pública que
      // qualquer destinatário usaria (GET /public/experiences/<slug>/, já
      // testada e usada por PublicExperienceView) só para enriquecer a tela
      // de sucesso — a publicação em si já está feita e confirmada acima,
      // então uma falha aqui nunca vira um erro de publicação.
      let title = "";
      let theme = "";
      try {
        const published = await fetchPublicExperience(result.slug);
        title = published.title;
        theme = published.theme;
      } catch {
        // Preview cosmético apenas — a tela de sucesso abaixo já lida com
        // title/theme vazios.
      }

      // Any 200 here — first publish or an idempotent republish of an
      // already-published draft — is treated identically as success; the
      // backend guarantees the same slug either way, no special-casing.
      setPublishPhase({ kind: "published", slug: result.slug, title, theme });
    } catch (error) {
      // Publish failing never touches CheckoutView's own phase — the
      // approved-payment state (this component even being rendered) is
      // entirely unaffected by a publish error.
      setPublishPhase({ kind: "error", message: extractPublishErrorMessage(error) });
    }
  }

  // Tela de sucesso dedicada — substitui inteiramente o cartão "Pagamento
  // aprovado!" acima dela. Antes disto, publicar redirecionava o CRIADOR
  // automaticamente para /e/[slug] (router.push após 1.2s, ver histórico de
  // git) — a mesma rota pública que o DESTINATÁRIO usa, fazendo o criador
  // "abrir a própria homenagem" como se fosse quem a recebeu. O criador
  // publicou para outra pessoa; quem deve abrir /e/[slug] é essa pessoa, a
  // partir do link que o criador compartilhar — nunca automaticamente aqui.
  if (publishPhase.kind === "published") {
    return <PublishedSuccessBlock slug={publishPhase.slug} title={publishPhase.title} theme={publishPhase.theme} />;
  }

  return (
    <div className="flex flex-col items-center gap-4 rounded-3xl border border-green-400/30 bg-green-400/10 p-10 text-center backdrop-blur-xl">
      <span className="text-5xl">✓</span>
      <h2 className="text-2xl font-bold text-white">Pagamento aprovado!</h2>
      <p className="text-slate-300">Sua experiência foi paga com sucesso.</p>

      {publishPhase.kind === "idle" && (
        <button
          type="button"
          onClick={() => void handlePublish()}
          className="mt-2 rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
        >
          ✨ Publicar experiência
        </button>
      )}

      {publishPhase.kind === "publishing" && (
        <button
          type="button"
          disabled
          className="mt-2 flex items-center gap-3 rounded-full bg-yellow-400/50 px-6 py-3 font-semibold text-black/70"
        >
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-black/30 border-t-black" />
          Publicando...
        </button>
      )}

      {publishPhase.kind === "error" && (
        <div className="mt-2 flex flex-col items-center gap-3">
          <p className="text-sm text-red-300">{publishPhase.message}</p>
          <button
            type="button"
            onClick={() => void handlePublish()}
            className="rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
          >
            Tentar novamente
          </button>
        </div>
      )}

      <a
        href="/dashboard"
        className="mt-2 rounded-full border border-white/20 px-6 py-3 font-semibold text-white transition-colors hover:bg-white/10"
      >
        Ir para o Dashboard
      </a>
    </div>
  );
}

function PublishedSuccessBlock({ slug, title, theme }: { slug: string; title: string; theme: string }) {
  const [copyFeedback, setCopyFeedback] = useState<"idle" | "copied" | "failed">("idle");

  // Seguro acessar window/navigator direto no corpo do componente (sem
  // useEffect/guard de SSR): PublishedSuccessBlock só é montado a partir de
  // um publishPhase.kind === "published", e o estado inicial de
  // ApprovedBlock é sempre "idle" — esse estado só vira "published" depois
  // de um clique do usuário + uma chamada assíncrona já resolvida, nunca
  // durante a passada de SSR/hidratação inicial (mesmo raciocínio já usado
  // em ExperienceCard.tsx/GalaxyChapter.tsx para navigator.clipboard/
  // getAccessToken em handlers, aqui só estendido ao corpo do componente
  // porque a própria montagem já é 100% pós-interação do usuário).
  const publicUrl = `${window.location.origin}/e/${slug}`;
  const canShare = typeof navigator.share === "function";

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(publicUrl);
      setCopyFeedback("copied");
    } catch {
      setCopyFeedback("failed");
    } finally {
      setTimeout(() => setCopyFeedback("idle"), 2500);
    }
  }

  async function shareLink() {
    try {
      await navigator.share({
        title: title || "MemoVerse",
        text: "Preparei uma experiência especial para você no MemoVerse ✨",
        url: publicUrl,
      });
    } catch {
      // Usuário cancelou o compartilhamento nativo, ou o navegador recusou
      // — nunca vira um erro visível; "Copiar link" continua ali do lado
      // como alternativa sempre disponível.
    }
  }

  return (
    <div className="flex flex-col items-center gap-6 rounded-3xl border border-green-400/30 bg-green-400/10 p-8 text-center backdrop-blur-xl sm:p-10">
      <span className="text-5xl">✨</span>

      <div>
        <h2 className="text-2xl font-bold text-white">Experiência publicada!</h2>
        <p className="mt-2 text-slate-300">Sua experiência está pronta para ser compartilhada.</p>
      </div>

      {theme && (
        <div className="w-full max-w-xs">
          <ThemeVisual theme={theme} />
          {title && <p className="mt-3 text-sm font-semibold text-white">{title}</p>}
        </div>
      )}

      <div className="w-full text-left">
        <p className="mb-2 text-center text-sm font-semibold text-slate-300">🔗 Link da experiência</p>
        <div className="break-all rounded-2xl border border-white/10 bg-black/30 p-4 text-center text-sm text-slate-200">
          {publicUrl}
        </div>
      </div>

      <div className="flex w-full flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => void copyLink()}
          className="flex-1 rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-[1.02] active:scale-95"
        >
          {copyFeedback === "copied"
            ? "✓ Link copiado!"
            : copyFeedback === "failed"
              ? "Não copiou — selecione o link acima"
              : "Copiar link"}
        </button>

        {canShare && (
          <button
            type="button"
            onClick={() => void shareLink()}
            className="flex-1 rounded-full border border-white/20 px-6 py-3 font-semibold text-white transition-colors hover:bg-white/10"
          >
            Compartilhar
          </button>
        )}
      </div>

      <div className="mt-2 flex w-full flex-col gap-3 sm:flex-row">
        <a
          href="/dashboard"
          className="flex-1 rounded-full bg-white/10 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-white/20"
        >
          Voltar para minhas experiências
        </a>
        {/* Ação secundária, nunca automática — o criador decide se quer ver
            a própria homenagem antes de compartilhar. */}
        <a
          href={`/e/${slug}`}
          className="flex-1 rounded-full border border-white/10 px-6 py-3 text-sm font-semibold text-slate-300 transition-colors hover:bg-white/10"
        >
          Visualizar experiência
        </a>
      </div>
    </div>
  );
}

function FailedBlock({ status, onRetry }: { status: PaymentStatus; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-3xl border border-red-400/30 bg-red-400/10 p-10 text-center backdrop-blur-xl">
      <span className="text-5xl">✕</span>
      <h2 className="text-2xl font-bold text-white">{statusLabel(status)}</h2>
      <p className="text-slate-300">Você pode tentar novamente com Pix ou cartão.</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
      >
        Tentar novamente
      </button>
    </div>
  );
}

function ErrorBlock({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-3xl border border-red-400/30 bg-red-400/10 p-10 text-center backdrop-blur-xl">
      <span className="text-5xl">⚠</span>
      <p className="text-slate-200">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-105"
      >
        Tentar novamente
      </button>
    </div>
  );
}
