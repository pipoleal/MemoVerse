"use client";

import { useCallback, useState } from "react";
import axios from "axios";

import { api } from "@/lib/api";

export type CreateDiscountPayload = {
  email: string;
  plan_code: string;
  price: string;
  note?: string;
};

export type CreateDiscountState = {
  loading: boolean;
  error: string | null;
  createDiscount: (payload: CreateDiscountPayload) => Promise<boolean>;
  clearError: () => void;
};

// Espelha apps.ops.views.PlanDiscountListView.post — o backend é quem
// decide (plano válido/ativo, sem desconto ativo duplicado para o mesmo
// par e-mail+plano). Este hook só chama POST e repassa a mensagem de erro
// real do backend (400/409), nunca inventa uma genérica quando o backend
// já explicou o motivo.
export function useCreateDiscount(): CreateDiscountState {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createDiscount = useCallback(async (payload: CreateDiscountPayload): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      await api.post("/ops/9b4/discounts/", payload);
      return true;
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data && typeof err.response.data === "object") {
        const data = err.response.data as Record<string, unknown>;
        if (typeof data.detail === "string") {
          setError(data.detail);
        } else {
          // Erros de validação do DRF vêm como {campo: ["mensagem"]} —
          // pega a primeira mensagem do primeiro campo com erro em vez de
          // um genérico "algo deu errado".
          const firstField = Object.values(data)[0];
          const firstMessage = Array.isArray(firstField) ? firstField[0] : undefined;
          setError(typeof firstMessage === "string" ? firstMessage : "Não foi possível criar este desconto agora.");
        }
      } else {
        setError("Não foi possível criar este desconto agora.");
      }
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, createDiscount, clearError: () => setError(null) };
}
