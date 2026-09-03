import { api } from "./api";

// Instrumentação mínima e anônima do funil de conversão (POST /api/events/,
// ver backend/app/apps/telemetry) — existe porque, até esta etapa, não
// havia NENHUMA forma de saber em qual etapa um visitante abandonou (o
// painel /admin só mostra o estado final de um draft/pagamento, nunca a
// jornada). Nunca envia e-mail/nome/payload de conteúdo — só o nome do
// evento, um session_id opaco e metadados pequenos (ex.: qual plano).
//
// Fire-and-forget por design, mesmo padrão já usado no claim de draft
// anônimo (RegisterForm/LoginForm): uma falha aqui (rede, backend fora do
// ar, localStorage indisponível) nunca deve aparecer para quem está usando
// o produto, então logEvent nunca lança e ninguém precisa dar `await`
// nela.
export type FunnelEventName =
  | "preview_completed"
  | "pricing_viewed"
  | "signup_started"
  | "signup_completed"
  | "checkout_viewed"
  | "payment_started"
  | "payment_failed"
  | "payment_approved"
  | "publication_completed";

const SESSION_KEY = "memoverse.funnel-session-id";

function isBrowser() {
  return typeof window !== "undefined";
}

// Um id aleatório por navegador, persistido em localStorage (sobrevive a
// navegação entre páginas e a fechar/reabrir a aba) — nunca um identificador
// de usuário, nunca derivado de e-mail/IP. Serve só para agrupar os eventos
// de UMA sessão de criação ao reconstruir o funil depois (ver
// apps.telemetry.models.FunnelEvent).
function getSessionId(): string {
  if (!isBrowser()) return "";
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const generated =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(SESSION_KEY, generated);
    return generated;
  } catch {
    // Armazenamento indisponível (modo privado, quota) — degrada para "sem
    // correlação entre eventos", nunca quebra a chamada em si.
    return "";
  }
}

export function logEvent(
  name: FunnelEventName,
  options?: { draftId?: string; metadata?: Record<string, string | number | boolean> }
): void {
  if (!isBrowser()) return;

  void api
    .post("/events/", {
      name,
      session_id: getSessionId(),
      draft_id: options?.draftId ?? "",
      metadata: options?.metadata ?? {},
    })
    .catch(() => {
      // ignorado de propósito — ver comentário no topo do arquivo.
    });
}
