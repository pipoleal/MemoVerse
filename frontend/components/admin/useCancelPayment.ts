"use client";

import { useCallback, useState } from "react";
import axios from "axios";

import { api } from "@/lib/api";

export type CancelPaymentState = {
  loading: boolean;
  error: string | null;
  cancelPayment: (paymentId: string) => Promise<boolean>;
  clearError: () => void;
};

// Espelha apps.ops.views.PaymentCancelView — cancela só LOCALMENTE (nunca
// chama a Mercado Pago). O backend decide se o Payment ainda está num
// status ativo; este hook só repassa a mensagem real dele.
export function useCancelPayment(): CancelPaymentState {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cancelPayment = useCallback(async (paymentId: string): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      await api.post(`/ops/9b4/payments/${paymentId}/cancel/`);
      return true;
    } catch (err) {
      if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") {
        setError(err.response.data.detail);
      } else {
        setError("Não foi possível cancelar este pagamento agora.");
      }
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, cancelPayment, clearError: () => setError(null) };
}
