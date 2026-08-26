import { api } from "./api";

// Espelha exatamente apps.accounts.serializers.password_reset — nenhum
// campo além do que o backend realmente aceita/devolve. Em nenhum desses
// tipos existe um campo de código de RESPOSTA: o backend nunca devolve o
// código em nenhuma chamada (ver auditoria), só o recebe como entrada em
// verify/confirm.

export async function requestPasswordReset(email: string): Promise<void> {
  await api.post("/auth/password-reset/request/", { email });
}

export async function verifyPasswordResetCode(email: string, code: string): Promise<void> {
  await api.post("/auth/password-reset/verify/", { email, code });
}

export async function confirmPasswordReset(
  email: string,
  code: string,
  newPassword: string
): Promise<void> {
  await api.post("/auth/password-reset/confirm/", {
    email,
    code,
    new_password: newPassword,
  });
}
