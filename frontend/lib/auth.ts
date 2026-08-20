import axios from "axios";

import { api } from "./api";
import { saveTokens, clearTokens, clearUserFirstName, getRefreshToken } from "./storage";

type LoginData = {
  email: string;
  password: string;
};

export async function login(data: LoginData) {
  try {
    const response = await api.post("/auth/login/", data);

    saveTokens(response.data.access, response.data.refresh);

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const status = error.response?.status;
      const respData = error.response?.data;
      throw { status, data: respData, message: error.message };
    }

    throw error;
  }
}

export async function logout() {
  // Etapa 8: revoga o refresh token no servidor antes de limpar o storage
  // local — best-effort de propósito. Uma falha de rede/servidor nunca
  // pode impedir o logout visível: o usuário sempre sai da conta local,
  // mesmo que a revogação do lado do servidor não tenha sido confirmada
  // (ex.: já estava sem conexão).
  const refresh = getRefreshToken();
  if (refresh) {
    try {
      await api.post("/auth/logout/", { refresh });
    } catch {
      // ignorado de propósito — ver comentário acima
    }
  }

  try {
    clearTokens();
    clearUserFirstName();
  } finally {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }
}