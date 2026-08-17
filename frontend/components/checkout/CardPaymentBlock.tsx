"use client";

import { useEffect, useState } from "react";
import { CardPayment, initMercadoPago } from "@mercadopago/sdk-react";
import type { ICardPaymentFormData, ICardPaymentBrickPayer } from "@mercadopago/sdk-react/esm/bricks/cardPayment/type";
import type { IBrickError } from "@mercadopago/sdk-react/esm/bricks/util/types/common";

import type { CardCheckoutData } from "@/lib/checkout";

// initMercadoPago must run exactly once per page load (calling it again just
// re-creates the same global SDK instance) — a module-level flag survives
// remounts of this component within the same page without reinitializing.
let mercadoPagoInitialized = false;

function ensureMercadoPagoInitialized(publicKey: string) {
  if (mercadoPagoInitialized) return;
  initMercadoPago(publicKey, { locale: "pt-BR" });
  mercadoPagoInitialized = true;
}

type Props = {
  // Only used to initialize the Brick's own installment/fee display — the
  // backend never reads this value; Payment.amount is always frozen
  // server-side from Plan.price (see CheckoutService._create_attempt).
  amount: number;
  payerEmail?: string;
  onSubmit: (data: CardCheckoutData) => Promise<void>;
};

export default function CardPaymentBlock({ amount, payerEmail, onSubmit }: Props) {
  const publicKey = process.env.NEXT_PUBLIC_MP_PUBLIC_KEY;

  const [ready, setReady] = useState(false);
  const [brickError, setBrickError] = useState<string | null>(null);

  useEffect(() => {
    if (publicKey) ensureMercadoPagoInitialized(publicKey);
  }, [publicKey]);

  if (!publicKey) {
    // Never renders the Brick without a public key — no silent fallback that
    // could look like a working card form.
    return (
      <div className="rounded-3xl border border-red-400/30 bg-red-400/10 p-6 text-center text-sm text-red-200">
        Pagamento por cartão indisponível no momento.
      </div>
    );
  }

  async function handleSubmit(formData: ICardPaymentFormData<ICardPaymentBrickPayer>) {
    setBrickError(null);
    try {
      await onSubmit({
        token: formData.token,
        paymentMethodId: formData.payment_method_id,
        installments: formData.installments,
        issuerId: formData.issuer_id || undefined,
      });
    } catch (error) {
      setBrickError(error instanceof Error ? error.message : "Não foi possível processar o pagamento.");
      // Re-throwing keeps the Brick's own contract: onSubmit rejecting tells
      // it the submission failed, so it re-enables its submit button instead
      // of staying stuck in a "processing" state.
      throw error;
    }
  }

  function handleError(error: IBrickError) {
    setBrickError("Não foi possível carregar o formulário de pagamento. Tente novamente.");
    // Never logs formData/token — only the Brick's own error object, which
    // never carries card data.
    console.error("[CardPaymentBrick]", error);
  }

  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
      {!ready && (
        <div className="flex flex-col items-center gap-4 py-10 text-center">
          <span className="h-8 w-8 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
          <p className="text-sm text-slate-300">Carregando formulário de pagamento...</p>
        </div>
      )}

      {brickError && <p className="mb-3 text-sm text-red-300">{brickError}</p>}

      <div style={{ display: ready ? "block" : "none" }}>
        <CardPayment
          initialization={{
            amount,
            payer: payerEmail ? { email: payerEmail } : undefined,
          }}
          customization={{ visual: { style: { theme: "dark" } } }}
          onReady={() => setReady(true)}
          onError={handleError}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}
