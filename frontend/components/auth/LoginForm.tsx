"use client";

import axios from "axios";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { login } from "@/lib/auth";
import { clearAnonymousDraft, getAnonymousDraft } from "@/lib/anonymousDraft";
import { clearPendingExperience, hasPendingExperience, savePendingExperienceDraft } from "@/lib/pendingExperience";
import { clearPendingGalaxySave, getPendingGalaxySave } from "@/lib/pendingGalaxySave";
import { saveExperienceToGalaxy } from "@/lib/publicExperience";

import Button from "../ui/Button";
import Input from "./Input";
import PasswordInput from "./PasswordInput";

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function errorMessage(submitError: unknown, loginSucceeded: boolean) {
    if (axios.isAxiosError(submitError) && !submitError.response) {
      return "Não foi possível conectar ao servidor. Verifique se o backend está em execução e tente novamente.";
    }

    // login() já concluiu (token salvo) quando este erro acontece — a falha
    // é em salvar a experiência pendente, não nas credenciais. Nunca sugerir
    // "confira seus dados" aqui: o login em si funcionou.
    if (loginSucceeded) {
      return "Login realizado, mas não foi possível salvar sua experiência pendente. Tente novamente.";
    }

    return "Não foi possível entrar. Confira seus dados e tente novamente.";
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    let loginSucceeded = false;
    try {
      await login({ email, password });
      loginSucceeded = true;

      // Etapa 10: mesmo mecanismo de RegisterForm.tsx — ver comentário lá,
      // incluindo claimedDraftId (redireciona pro checkout em vez do
      // dashboard quando o claim funcionou).
      const anonymousDraft = getAnonymousDraft();
      let claimedDraftId: string | null = null;
      if (anonymousDraft) {
        try {
          await api.post(`/experiences/drafts/${anonymousDraft.draftId}/claim/`, {
            claim_token: anonymousDraft.claimToken,
          });
          claimedDraftId = anonymousDraft.draftId;
        } catch {
          // ignorado de propósito — ver RegisterForm.tsx
        } finally {
          clearAnonymousDraft();
        }
      }

      if (hasPendingExperience()) {
        await savePendingExperienceDraft();
        clearPendingExperience();
      }

      // Etapa Minha Galáxia (destinatário): "Criar minha Galáxia" salvou o
      // slug aqui antes de mandar para /login (ver GalaxyChapter.tsx) —
      // best-effort de propósito, mesmo padrão do claim acima: login já
      // concluído com sucesso, uma falha aqui (slug expirado nesse meio
      // tempo, rede) nunca deve travar o usuário sem saída.
      const pendingGalaxySave = getPendingGalaxySave();
      let galaxySaved = false;
      if (pendingGalaxySave) {
        try {
          await saveExperienceToGalaxy(pendingGalaxySave.slug);
          galaxySaved = true;
        } catch {
          // ignorado de propósito — ver comentário acima
        } finally {
          clearPendingGalaxySave();
        }
      }

      if (galaxySaved) {
        router.push("/dashboard/galaxia");
        return;
      }
      router.push(claimedDraftId ? `/checkout/${claimedDraftId}` : "/dashboard");
    } catch (submitError) {
      setError(errorMessage(submitError, loginSucceeded));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Input label="E-mail" type="email" name="email" placeholder="Digite seu e-mail" value={email} onChange={(event) => setEmail(event.target.value)} required />
      <PasswordInput label="Senha" name="password" placeholder="Digite sua senha" value={password} onChange={(event) => setPassword(event.target.value)} required />
      <div className="flex justify-end">
        <Link
          href="/forgot-password"
          className="text-sm text-slate-300 underline-offset-4 transition hover:text-yellow-300 hover:underline"
        >
          Esqueceu sua senha?
        </Link>
      </div>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      <Button type="submit" className="w-full disabled:cursor-not-allowed disabled:opacity-80" disabled={loading}>
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-black/30 border-t-black" />
            Entrando...
          </span>
        ) : (
          "Entrar"
        )}
      </Button>
    </form>
  );
}
