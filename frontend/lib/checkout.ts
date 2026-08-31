import axios from "axios";

import { api } from "./api";

// Minimal plan info — exactly what apps/payments/serializers/status.py
// still returns (DraftPaymentStatusView never needed price/features: the
// resume flow always re-POSTs to /checkout/ to get a full Plan).
export type PlanSummary = {
  code: string;
  name: string;
};

export type PlanFeatures = {
  duration_days: number | null;
  is_lifetime: boolean;
  galaxy_live_enabled: boolean;
  // Ready-to-render commercial differentials, in display order — the
  // backend is the only source (Plan.features["highlights"], seeded in
  // apps/payments/migrations/0006_add_plan_highlights.py). Never composed,
  // translated, or hardcoded on the frontend.
  highlights: string[];
};

// Full plan info — GET /payments/plans/ and CheckoutResponse.plan both
// return exactly this shape (apps/payments/serializers/plans.py and the
// expanded PlanSummarySerializer in serializers/checkout.py).
export type Plan = {
  code: string;
  name: string;
  // DRF serializes DecimalField as a string by default (avoids float
  // rounding) — always Number(plan.price) before formatting or passing it
  // anywhere numeric (e.g. CardPaymentBlock's `amount` prop).
  price: string;
  currency: string;
  features: PlanFeatures;
};

// Single source of price-formatting logic — never format a plan price
// anywhere else, to avoid the same value drifting across components.
export function formatPlanPrice(price: string, currency: string = "BRL"): string {
  return Number(price).toLocaleString("pt-BR", { style: "currency", currency });
}

// Comunicação comercial: "Vitalício" virou "Anual" só na apresentação.
// Plan.name (banco, seedado em
// payments/migrations/0005_seed_commercial_plans.py) e
// duration_days/is_lifetime/preço (ver
// experiences/services/publication_service.py) continuam exatamente como
// estão — nenhuma lógica de cobrança/duração é tocada aqui, só o texto
// exibido onde o nome do plano aparece (checkout, landing page).
export function displayPlanName(name: string): string {
  return name.replace(/Vitalício/gi, "Anual");
}

// "Disponível para sempre" (um dos highlights vindos do banco, ver
// payments/migrations/0006_add_plan_highlights.py) contradiria um plano
// agora chamado "Anual" na tela — mesmo tipo de substituição só de
// apresentação, nunca alterando o array que vem da API.
export function displayPlanHighlight(highlight: string): string {
  return highlight.replace(/Dispon[ií]vel para sempre/gi, "Disponível por 1 ano");
}

// "MemoVerse 1 Semana" -> "1 SEMANA" — um transform ao vivo do nome real do
// plano vindo da API, nunca um título hardcoded por plan_code (que poderia
// silenciosamente divergir de Plan.name no backend).
export function planCardTitle(name: string): string {
  return displayPlanName(name).replace(/^MemoVerse\s+/i, "").toUpperCase();
}

// Exactly the keys apps/payments/views/checkout.py::_checkout_payload_for
// may include — mp_order_id is always present, the rest only when the
// Mercado Pago Order response actually carried them.
export type CheckoutArtifacts = {
  mp_order_id: string;
  qr_code?: string;
  qr_code_base64?: string;
  ticket_url?: string;
  // "bank_transfer" (Pix) or "credit_card"/"debit_card" (card) — lets a
  // resumed checkout know which UI to show without guessing.
  payment_method_type?: string;
};

export type PaymentMethodChoice = "pix" | "card";

// Exactly the fields the Card Payment Brick's onSubmit callback provides
// (token, payment_method_id, installments — issuer_id optional) — never the
// card number/CVV, which the Brick never gives the frontend either.
export type CardCheckoutData = {
  token: string;
  paymentMethodId: string;
  installments: number;
  issuerId?: string;
};

// Mirrors apps/payments/models.py Payment.Status exactly.
export type PaymentStatus =
  | "pending"
  | "in_process"
  | "action_required"
  | "approved"
  | "rejected"
  | "cancelled"
  | "expired"
  | "refunded";

export const ACTIVE_PAYMENT_STATUSES: PaymentStatus[] = ["pending", "in_process", "action_required"];
// "rejected"/"cancelled"/"expired" per the task's explicit stop-polling
// list, plus "refunded": also terminal and not in ACTIVE_PAYMENT_STATUSES,
// so it must never fall through to a silent new checkout attempt either.
export const FAILED_PAYMENT_STATUSES: PaymentStatus[] = ["rejected", "cancelled", "expired", "refunded"];

export type CheckoutResponse = {
  payment_id: string;
  status: PaymentStatus;
  plan: Plan;
  checkout: CheckoutArtifacts;
};

export type PaymentStatusSummary = {
  payment_id: string;
  status: PaymentStatus;
  attempt_number: number;
  plan: PlanSummary;
};

export type DraftPaymentStatus = {
  draft_status: string;
  payment: PaymentStatusSummary | null;
};

export async function fetchDraftPaymentStatus(draftId: string): Promise<DraftPaymentStatus> {
  const response = await api.get<DraftPaymentStatus>(`/payments/drafts/${draftId}/status/`);
  return response.data;
}

// GET /payments/plans/ — public (no auth required), only ever returns
// active/purchasable plans, already ordered by price. The frontend never
// hardcodes a plan_code or price anywhere; this is the only source.
export async function fetchActivePlans(): Promise<Plan[]> {
  const response = await api.get<Plan[]>("/payments/plans/");
  return response.data;
}

// POST /payments/drafts/<id>/checkout/ is idempotent on the backend: if an
// active Payment already exists for this draft+plan, it is reused (no new
// Mercado Pago Order is created) — see CheckoutService.start_checkout. Safe
// to call again on remount/page reload/retry after a gateway error.
//
// card is only read when method === "card" — for "pix" the request body is
// exactly {plan_code} as before, unchanged.
export async function createOrResumeCheckout(
  draftId: string,
  planCode: string,
  method: PaymentMethodChoice = "pix",
  card?: CardCheckoutData
): Promise<CheckoutResponse> {
  const body: Record<string, unknown> = { plan_code: planCode, payment_method: method };

  if (method === "card" && card) {
    body.token = card.token;
    body.payment_method_id = card.paymentMethodId;
    body.installments = card.installments;
    if (card.issuerId) body.issuer_id = card.issuerId;
  }

  const response = await api.post<CheckoutResponse>(`/payments/drafts/${draftId}/checkout/`, body);
  return response.data;
}

// Present only on the 409 CONFLICT body from DraftCheckoutView — an active
// Payment already exists for this draft, but for a different plan_code than
// the one just requested.
export function getActiveConflictPlanCode(error: unknown): string | null {
  if (axios.isAxiosError(error) && error.response?.status === 409) {
    const code = error.response.data?.active_plan_code;
    if (typeof code === "string") return code;
  }
  return null;
}

export function extractCheckoutErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Não foi possível conectar ao servidor.";
  }
  return "Não foi possível carregar o pagamento. Tente novamente.";
}
