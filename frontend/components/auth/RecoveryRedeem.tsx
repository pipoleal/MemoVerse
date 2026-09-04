"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { redeemRecoveryToken } from "@/lib/recovery";
import { saveTokens, saveUserFirstName } from "@/lib/storage";

type State = { kind: "idle" } | { kind: "loading" } | { kind: "error"; message: string };

// Client-side de propósito (não redireciona a partir do backend): o access/
// refresh nunca deve passar pela URL (histórico do navegador, logs,
// referrer) — só o token de uso único do link passa por aí. Este
// componente troca esse token pelo par de verdade (POST /recovery/redeem/)
// e SÓ ENTÃO guarda a sessão como um login normal guardaria (ver
// lib/auth.ts login()).
//
// Nunca dispara sozinho no mount (nem num useEffect): scanners de link
// corporativos (proteção de e-mail da própria empresa do cliente,
// preview automático de app de mensagens) costumam abrir a página e
// executar JavaScript para checar segurança/gerar preview, ANTES de
// qualquer humano clicar de verdade — se o resgate disparasse sozinho, o
// token de uso único seria consumido por esse robô, e a pessoa real veria
// "link inválido" ao clicar. Exigir um clique explícito aqui não é 100%
// à prova de scanner (alguns simulam clique), mas elimina o caso comum
// (scanner que só abre a página).
export default function RecoveryRedeem({ token }: { token: string }) {
  const router = useRouter();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function handleContinue() {
    setState({ kind: "loading" });
    try {
      const result = await redeemRecoveryToken(token);
      saveTokens(result.access, result.refresh);
      if (result.firstName) saveUserFirstName(result.firstName);
      router.replace(`/experience/edit/${result.draftId}`);
    } catch (error) {
      setState({ kind: "error", message: (error as Error).message });
    }
  }

  if (state.kind === "loading") {
    return (
      <div className="flex flex-col items-center gap-4 py-6">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-yellow-400/30 border-t-yellow-400" />
        <p className="text-sm text-slate-400">Levando você direto para o seu presente...</p>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <div className="flex flex-col items-center gap-4 py-2 text-center">
        <p className="text-sm text-red-300">{state.message}</p>
        <a
          href="/login"
          className="rounded-full bg-yellow-300 px-6 py-3 font-semibold text-slate-950 transition hover:bg-yellow-200"
        >
          Ir para o login
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 py-2 text-center">
      <p className="text-sm text-slate-300">Seu presente continua salvo, esperando por você.</p>
      <button
        type="button"
        onClick={() => void handleContinue()}
        className="rounded-full bg-yellow-300 px-6 py-3 font-semibold text-slate-950 transition hover:bg-yellow-200"
      >
        Continuar meu presente
      </button>
    </div>
  );
}
