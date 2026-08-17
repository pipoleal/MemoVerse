"use client";

import { useEffect, useRef, useState } from "react";

import CardPaymentBlock from "./CardPaymentBlock";
import {
  createOrResumeCheckout,
  extractCheckoutErrorMessage,
  fetchDraftPaymentStatus,
  getActiveConflictPlanCode,
  FAILED_PAYMENT_STATUSES,
  type CardCheckoutData,
  type CheckoutResponse,
  type PaymentMethodChoice,
  type PaymentStatus,
} from "@/lib/checkout";
import { extractPublishErrorMessage, publishDraft } from "@/lib/publish";

// No plan-selection UI exists anywhere in the product yet (confirmed: no
// `plan` field on the wizard's Experience type, no plan picker component).
// "essential" is the one active Plan.code the backend already accepts for
// this exact endpoint — see apps/payments/migrations/0002_seed_initial_plans.py.
// This is a placeholder until a real plan-selection step exists.
const DEFAULT_PLAN_CODE = "essential";

// Same placeholder debt as DEFAULT_PLAN_CODE above: no plans endpoint exists
// yet for the frontend to read a real price from. The Card Payment Brick
// requires a numeric `initialization.amount` purely to render its own
// installment/fee simulator — this value is NEVER sent to the backend as
// the charge amount and is NEVER trusted by it either way (Payment.amount is
// always frozen server-side from Plan.price — see
// CheckoutService._create_attempt). Matches the "essential" plan's price
// from apps/payments/migrations/0002_seed_initial_plans.py.
const DEFAULT_PLAN_DISPLAY_AMOUNT = 29.99;

const POLL_INTERVAL_MS = 5000;

type Phase =
  | { kind: "loading" }
  // No payment exists yet for this draft: the user must actively choose Pix
  // or Cartão before any Payment/Order is created — see startCheckout, only
  // ever called from here after an explicit choice.
  | { kind: "selecting_method" }
  | { kind: "creating"; method: PaymentMethodChoice }
  | { kind: "awaiting_payment"; checkout: CheckoutResponse; method: PaymentMethodChoice }
  | { kind: "approved"; checkout: CheckoutResponse | null }
  | { kind: "payment_failed"; status: PaymentStatus; checkout: CheckoutResponse | null }
  | { kind: "error"; message: string };

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
      setPhase({ kind: "payment_failed", status: result.status, checkout: result });
    } else {
      setPhase({ kind: "awaiting_payment", checkout: result, method });
    }
  }

  async function initialize() {
    setPhase({ kind: "loading" });

    try {
      const data = await fetchDraftPaymentStatus(draftId);

      if (!data.payment) {
        // Nothing started yet: let the user choose Pix or Cartão instead of
        // silently generating a Pix order, as the flow used to do.
        setPhase({ kind: "selecting_method" });
        return;
      }

      if (data.payment.status === "approved") {
        setPhase({ kind: "approved", checkout: null });
        return;
      }

      if (FAILED_PAYMENT_STATUSES.includes(data.payment.status)) {
        setPhase({ kind: "payment_failed", status: data.payment.status, checkout: null });
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
              ? { kind: "payment_failed", status: paymentStatus, checkout: current.checkout }
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

        {phase.kind !== "error" && (
          <div className="mt-8 rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl">
            <PlanSummaryBlock checkout={"checkout" in phase ? phase.checkout : null} />
          </div>
        )}

        <div className="mt-6">
          {phase.kind === "loading" && <LoadingBlock message="Carregando pagamento..." />}

          {phase.kind === "selecting_method" && (
            <MethodSelectionBlock
              onChoosePix={() => void startCheckout(DEFAULT_PLAN_CODE, "pix")}
              onSubmitCard={(cardData) => startCheckout(DEFAULT_PLAN_CODE, "card", cardData)}
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
              onRetry={() => setPhase({ kind: "selecting_method" })}
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

function PlanSummaryBlock({ checkout }: { checkout: CheckoutResponse | null }) {
  if (!checkout) {
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
      <p className="mt-1 text-xl font-bold text-white">{checkout.plan.name}</p>
      {/* The backend never returns a price for this endpoint today (only
          plan code/name) — showing a number here would mean inventing data
          not backed by any API response, so it is intentionally omitted. */}
    </div>
  );
}

function MethodSelectionBlock({
  onChoosePix,
  onSubmitCard,
}: {
  onChoosePix: () => void;
  onSubmitCard: (cardData: CardCheckoutData) => Promise<void>;
}) {
  const [tab, setTab] = useState<PaymentMethodChoice>("pix");

  return (
    <div className="flex flex-col gap-6">
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
        <CardPaymentBlock amount={DEFAULT_PLAN_DISPLAY_AMOUNT} onSubmit={onSubmitCard} />
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
  | { kind: "published"; slug: string }
  | { kind: "error"; message: string };

function ApprovedBlock({ draftId }: { draftId: string }) {
  const [publishPhase, setPublishPhase] = useState<PublishPhase>({ kind: "idle" });
  const [linkCopyFeedback, setLinkCopyFeedback] = useState<"idle" | "copied" | "failed">("idle");

  async function handlePublish() {
    // Guards against a double click firing two requests — once published,
    // this branch is also never reachable again since the button is
    // replaced by the link block below.
    if (publishPhase.kind === "publishing" || publishPhase.kind === "published") return;

    setPublishPhase({ kind: "publishing" });

    try {
      // draftId is exactly the one this whole page was loaded with (passed
      // straight through from CheckoutView, itself the /checkout/[draftId]
      // route param) — never re-derived or guessed here.
      const result = await publishDraft(draftId);
      // Any 200 here — first publish or an idempotent republish of an
      // already-published draft — is treated identically as success; the
      // backend guarantees the same slug either way, no special-casing.
      setPublishPhase({ kind: "published", slug: result.slug });
    } catch (error) {
      // Publish failing never touches CheckoutView's own phase — the
      // approved-payment state (this component even being rendered) is
      // entirely unaffected by a publish error.
      setPublishPhase({ kind: "error", message: extractPublishErrorMessage(error) });
    }
  }

  const publicUrl = publishPhase.kind === "published" ? `${window.location.origin}/e/${publishPhase.slug}` : null;

  async function copyPublicLink() {
    if (!publicUrl) return;

    try {
      await navigator.clipboard.writeText(publicUrl);
      setLinkCopyFeedback("copied");
    } catch {
      setLinkCopyFeedback("failed");
    } finally {
      setTimeout(() => setLinkCopyFeedback("idle"), 2500);
    }
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

      {publishPhase.kind === "published" && publicUrl && (
        <div className="mt-2 flex w-full flex-col items-center gap-3">
          <p className="text-sm font-semibold text-green-300">✨ Experiência publicada!</p>

          <div className="w-full break-all rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-slate-300">
            {publicUrl}
          </div>

          <div className="flex w-full flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => void copyPublicLink()}
              className="flex-1 rounded-full bg-yellow-400 px-6 py-3 font-semibold text-black transition-transform hover:scale-[1.02] active:scale-95"
            >
              {linkCopyFeedback === "copied" ? "✓ Link copiado" : "Copiar link"}
            </button>

            <a
              href={publicUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 rounded-full border border-white/20 px-6 py-3 font-semibold text-white transition-colors hover:bg-white/10"
            >
              Abrir experiência
            </a>
          </div>

          {linkCopyFeedback === "failed" && (
            <p className="text-xs text-red-300">Não foi possível copiar automaticamente. Selecione o link acima manualmente.</p>
          )}
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
