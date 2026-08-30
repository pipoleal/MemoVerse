"use client";

import { useCallback, useState } from "react";
import axios from "axios";

import { api } from "@/lib/api";

export type DeleteDiscountState = {
  loading: boolean;
  error: string | null;
  deleteDiscount: (discountId: string) => Promise<boolean>;
  clearError: () => void;
};

// Espelha apps.ops.views.PlanDiscountDeleteView — sempre exclusão real
// (diferente de excluir usuário, aqui não há histórico financeiro a
// preservar: o Payment já congelou o valor cobrado independentemente de o
// desconto que o originou continuar existindo).
export function useDeleteDiscount(): DeleteDiscountState {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteDiscount = useCallback(async (discountId: string): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      await api.delete(`/ops/9b4/discounts/${discountId}/`);
      return true;
    } catch (err) {
      if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") {
        setError(err.response.data.detail);
      } else {
        setError("Não foi possível apagar este desconto agora.");
      }
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, deleteDiscount, clearError: () => setError(null) };
}
