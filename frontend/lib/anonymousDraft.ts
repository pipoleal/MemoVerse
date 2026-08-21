import { getAccessToken } from "./storage";

const KEY = "memoverse.anonymous-draft";

export type StoredAnonymousDraft = {
  draftId: string;
  claimToken: string;
};

function isBrowser() {
  return typeof window !== "undefined";
}

// localStorage (não sessionStorage): precisa sobreviver à navegação
// same-tab para /register ou /login (isso já sobreviveria em
// sessionStorage) E a fechar e reabrir a aba antes de terminar o cadastro
// (retomada — Etapa 10), que sessionStorage não cobre.
export function saveAnonymousDraft(draftId: string, claimToken: string) {
  if (!isBrowser()) return;
  try {
    localStorage.setItem(KEY, JSON.stringify({ draftId, claimToken } satisfies StoredAnonymousDraft));
  } catch {
    // Armazenamento indisponível (modo privado, quota) — degrada para "sem
    // retomada", nunca quebra o fluxo de criação em si.
  }
}

export function getAnonymousDraft(): StoredAnonymousDraft | null {
  if (!isBrowser()) return null;
  try {
    const stored = localStorage.getItem(KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as Partial<StoredAnonymousDraft>;
    if (typeof parsed.draftId !== "string" || typeof parsed.claimToken !== "string") {
      localStorage.removeItem(KEY);
      return null;
    }
    return { draftId: parsed.draftId, claimToken: parsed.claimToken };
  } catch {
    return null;
  }
}

export function clearAnonymousDraft() {
  if (!isBrowser()) return;
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignorado de propósito — mesmo padrão do resto do storage local
  }
}

// Cabeçalho de posse temporária para uma requisição sobre UM draft
// específico — nunca em querystring/URL (nunca aparece em log de acesso).
// Vazio quando o usuário já está autenticado (o interceptor de lib/api.ts
// já injeta Authorization nesse caso; os dois nunca coexistem na mesma
// requisição) ou quando o draft salvo localmente não é o mesmo desta
// chamada (nunca envia o token de um draft para o endpoint de outro).
export function draftClaimHeaders(draftId: string): Record<string, string> {
  if (getAccessToken()) return {};
  const stored = getAnonymousDraft();
  if (stored && stored.draftId === draftId) {
    return { "X-Draft-Claim-Token": stored.claimToken };
  }
  return {};
}
