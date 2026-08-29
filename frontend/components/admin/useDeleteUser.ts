"use client";

import { useCallback, useState } from "react";
import axios from "axios";

import { api } from "@/lib/api";

export type DeleteUserState = {
  loading: boolean;
  error: string | null;
  deleteUser: (userId: string) => Promise<boolean>;
  clearError: () => void;
};

// Espelha as salvaguardas de apps.ops.views.UserDeleteView — o backend é
// quem decide (não é: própria conta, não é: conta admin, sem nenhum
// Payment). Este hook só chama DELETE e repassa a mensagem de erro real
// do backend (400/409), nunca inventa uma genérica quando o backend já
// explicou o motivo.
export function useDeleteUser(): DeleteUserState {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteUser = useCallback(async (userId: string): Promise<boolean> => {
    setLoading(true);
    setError(null);

    try {
      await api.delete(`/ops/9b4/users/${userId}/`);
      return true;
    } catch (err) {
      if (axios.isAxiosError(err) && typeof err.response?.data?.detail === "string") {
        setError(err.response.data.detail);
      } else {
        setError("Não foi possível excluir este usuário agora.");
      }
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, error, deleteUser, clearError: () => setError(null) };
}
