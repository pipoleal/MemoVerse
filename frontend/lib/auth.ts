import axios from "axios";

import { api } from "./api";
import { saveTokens, clearTokens, clearUserFirstName } from "./storage";

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

export function logout() {
  try {
    clearTokens();
    clearUserFirstName();
  } finally {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }
}