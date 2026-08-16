import axios from "axios";

import { api } from "./api";

export type PlanSummary = {
  code: string;
  name: string;
};

// Exactly the keys apps/payments/views/checkout.py::_checkout_payload_for
// may include — mp_order_id is always present, the rest only when the
// Mercado Pago Order response actually carried them.
export type CheckoutArtifacts = {
  mp_order_id: string;
  qr_code?: string;
  qr_code_base64?: string;
  ticket_url?: string;
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
  plan: PlanSummary;
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

// POST /payments/drafts/<id>/checkout/ is idempotent on the backend: if an
// active Payment already exists for this draft+plan, it is reused (no new
// Mercado Pago Order is created) — see CheckoutService.start_checkout. Safe
// to call again on remount/page reload/retry after a gateway error.
export async function createOrResumeCheckout(draftId: string, planCode: string): Promise<CheckoutResponse> {
  const response = await api.post<CheckoutResponse>(`/payments/drafts/${draftId}/checkout/`, {
    plan_code: planCode,
  });
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
