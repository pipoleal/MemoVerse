const KEY = "memoverse.password-reset-flow";

export type PasswordResetStep = "request" | "verify" | "reset" | "success";

// Nunca inclui o código em si — só o suficiente para retomar a TELA certa
// depois de um reload (e-mail já digitado, e a validade estimada do
// código para o timer de UX). O backend é sempre quem realmente decide se
// o código ainda vale; isso aqui é só conveniência de tela, nunca uma
// fonte de verdade de segurança.
export type StoredPasswordResetFlow = {
  step: PasswordResetStep;
  email: string;
  codeExpiresAt: number | null;
};

function isBrowser() {
  return typeof window !== "undefined";
}

export function savePasswordResetFlow(state: StoredPasswordResetFlow) {
  if (!isBrowser()) return;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    // Storage indisponível (modo privado, cota) — degrada para "sem
    // retomada após reload", nunca quebra o fluxo em si.
  }
}

export function getPasswordResetFlow(): StoredPasswordResetFlow | null {
  if (!isBrowser()) return null;
  try {
    const stored = sessionStorage.getItem(KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as Partial<StoredPasswordResetFlow>;
    if (typeof parsed.step !== "string" || typeof parsed.email !== "string") {
      sessionStorage.removeItem(KEY);
      return null;
    }
    return {
      step: parsed.step as PasswordResetStep,
      email: parsed.email,
      codeExpiresAt: typeof parsed.codeExpiresAt === "number" ? parsed.codeExpiresAt : null,
    };
  } catch {
    return null;
  }
}

export function clearPasswordResetFlow() {
  if (!isBrowser()) return;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // ignorado de propósito, mesmo padrão do resto do storage aqui
  }
}
