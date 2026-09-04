import axios from "axios";

import { api } from "./api";

export type RecoveryRedeemResult = {
  access: string;
  refresh: string;
  draftId: string;
  firstName: string;
};

// POST /api/recovery/redeem/ (ver backend/app/apps/recovery/views.py) — o
// clique no link de e-mail/WhatsApp do fluxo de recuperação de carrinho cai
// aqui (ver app/r/[token]/page.tsx). Nunca distingue "expirado" de "já
// usado" de "não existe" — mesmo motivo de login nunca dizer qual dado
// exato está errado.
export async function redeemRecoveryToken(token: string): Promise<RecoveryRedeemResult> {
  try {
    const response = await api.post("/recovery/redeem/", { token });
    return {
      access: response.data.access,
      refresh: response.data.refresh,
      draftId: response.data.draft_id,
      firstName: response.data.first_name ?? "",
    };
  } catch (error) {
    if (axios.isAxiosError(error) && typeof error.response?.data?.detail === "string") {
      throw new Error(error.response.data.detail);
    }
    throw new Error("Este link não é mais válido. Faça login normalmente para continuar.");
  }
}
