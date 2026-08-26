"use client";

import axios from "axios";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  confirmPasswordReset,
  requestPasswordReset,
  verifyPasswordResetCode,
} from "@/lib/passwordReset";
import {
  clearPasswordResetFlow,
  getPasswordResetFlow,
  savePasswordResetFlow,
} from "@/lib/passwordResetFlowState";

import Button from "../ui/Button";
import Input from "./Input";
import PasswordInput from "./PasswordInput";

type Step = "request" | "verify" | "reset" | "success";

const CODE_TTL_MS = 10 * 60 * 1000;
const RESEND_COOLDOWN_SECONDS = 30;

// Mensagem idêntica à do backend (services/views password_reset) — nunca
// reformulada aqui, para que o texto continue sendo genérico de verdade
// (não revela se o e-mail existe) mesmo se o backend mudar a frase no
// futuro e alguém esquecer de sincronizar os dois lados.
const GENERIC_REQUEST_MESSAGE =
  "Se existir uma conta associada a este e-mail, enviaremos um código de recuperação.";

function errorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return "Não foi possível conectar ao servidor. Verifique se o backend está em execução e tente novamente.";
    }
    if (error.response.status === 429) {
      return "Muitas tentativas. Aguarde um pouco antes de tentar de novo.";
    }
    const data = error.response.data;
    if (typeof data?.detail === "string") return data.detail;
    if (typeof data?.new_password?.[0] === "string") return data.new_password[0];
    if (typeof data?.code?.[0] === "string") return data.code[0];
  }
  return fallback;
}

function formatSeconds(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default function ForgotPasswordFlow() {
  const router = useRouter();

  const [step, setStep] = useState<Step>("request");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const [codeExpiresAt, setCodeExpiresAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [resendCooldownUntil, setResendCooldownUntil] = useState<number | null>(null);

  // Retoma a tela de código depois de um reload — nunca a tela de nova
  // senha (o código em si nunca é persistido, só existe na memória do
  // componente entre o /verify/ e o /confirm/; um reload no meio da troca
  // de senha volta para pedir o código de novo, deliberadamente).
  useEffect(() => {
    const stored = getPasswordResetFlow();
    if (stored && stored.step === "verify") {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- hidratação client-only a partir do sessionStorage, só pode rodar depois do mount
      setEmail(stored.email);
      setCodeExpiresAt(stored.codeExpiresAt);
      setStep("verify");
    }
  }, []);

  // Um único ticker de 1s alimenta tanto o timer de validade do código
  // quanto o cooldown de reenvio — nenhum dos dois é usado para decidir
  // segurança, só para exibir contagem regressiva (o backend sempre
  // revalida tudo de novo em cada chamada).
  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  const codeSecondsLeft = codeExpiresAt ? Math.max(0, Math.round((codeExpiresAt - now) / 1000)) : 0;
  const resendSecondsLeft = resendCooldownUntil
    ? Math.max(0, Math.round((resendCooldownUntil - now) / 1000))
    : 0;

  async function sendCode(targetEmail: string) {
    await requestPasswordReset(targetEmail);
    const expiresAt = Date.now() + CODE_TTL_MS;
    setCodeExpiresAt(expiresAt);
    setResendCooldownUntil(Date.now() + RESEND_COOLDOWN_SECONDS * 1000);
    savePasswordResetFlow({ step: "verify", email: targetEmail, codeExpiresAt: expiresAt });
  }

  async function handleRequestSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await sendCode(email);
      setStep("verify");
    } catch (submitError) {
      // Mesmo em erro de rede/servidor, nunca diferenciar "e-mail existe"
      // de "não existe" — só falhas de infraestrutura chegam aqui, já que
      // o backend sempre responde 200 para qualquer e-mail válido no
      // formato.
      setError(errorMessage(submitError, "Não foi possível enviar o código. Tente novamente."));
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (resendSecondsLeft > 0) return;
    setLoading(true);
    setError("");
    setInfo("");
    try {
      await sendCode(email);
      setInfo("Enviamos um novo código para o seu e-mail.");
    } catch (submitError) {
      setError(errorMessage(submitError, "Não foi possível reenviar o código. Tente novamente."));
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifySubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await verifyPasswordResetCode(email, code);
      setStep("reset");
    } catch (submitError) {
      setError(errorMessage(submitError, "Código inválido ou expirado."));
    } finally {
      setLoading(false);
    }
  }

  async function handleResetSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (newPassword !== confirmNewPassword) {
      setError("As senhas não coincidem.");
      return;
    }

    setLoading(true);
    try {
      await confirmPasswordReset(email, code, newPassword);
      clearPasswordResetFlow();
      setStep("success");
    } catch (submitError) {
      // Um código que expirou/foi usado exatamente nesta janela (ex.: já
      // passou o TTL entre a tela 2 e a tela 3) cai aqui como qualquer
      // outro erro — a pessoa precisa voltar e pedir um novo, nunca uma
      // mensagem que distinga os motivos.
      setError(errorMessage(submitError, "Não foi possível alterar a senha. Solicite um novo código."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {step === "request" && (
        <form onSubmit={handleRequestSubmit} className="space-y-6">
          <Input
            label="E-mail"
            type="email"
            name="email"
            placeholder="Digite seu e-mail cadastrado"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
          <Button type="submit" className="w-full disabled:cursor-not-allowed disabled:opacity-80" disabled={loading}>
            {loading ? "Enviando..." : "Enviar código"}
          </Button>
        </form>
      )}

      {step === "verify" && (
        <form onSubmit={handleVerifySubmit} className="space-y-6">
          <p className="text-sm text-gray-300">{GENERIC_REQUEST_MESSAGE}</p>

          <Input
            label="Código de 6 dígitos"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            maxLength={6}
            placeholder="000000"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            required
            className="text-center text-2xl tracking-[0.5em]"
          />

          <p className="text-xs text-gray-400">
            {codeSecondsLeft > 0
              ? `O código expira em ${formatSeconds(codeSecondsLeft)}.`
              : "O código pode ter expirado — solicite um novo se a validação falhar."}
          </p>

          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
          {info && <p className="text-sm text-emerald-300">{info}</p>}

          <Button
            type="submit"
            className="w-full disabled:cursor-not-allowed disabled:opacity-80"
            disabled={loading || code.length !== 6}
          >
            {loading ? "Verificando..." : "Continuar"}
          </Button>

          <button
            type="button"
            onClick={handleResend}
            disabled={loading || resendSecondsLeft > 0}
            className="w-full text-center text-sm text-gray-400 underline-offset-4 transition hover:text-yellow-300 hover:underline disabled:cursor-not-allowed disabled:text-gray-600 disabled:no-underline"
          >
            {resendSecondsLeft > 0 ? `Reenviar código em ${formatSeconds(resendSecondsLeft)}` : "Reenviar código"}
          </button>
        </form>
      )}

      {step === "reset" && (
        <form onSubmit={handleResetSubmit} className="space-y-6">
          <PasswordInput
            label="Nova senha"
            name="newPassword"
            placeholder="Mínimo de 8 caracteres"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            required
          />
          <PasswordInput
            label="Confirmar nova senha"
            name="confirmNewPassword"
            placeholder="Repita a nova senha"
            value={confirmNewPassword}
            onChange={(event) => setConfirmNewPassword(event.target.value)}
            required
          />
          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
          <Button type="submit" className="w-full disabled:cursor-not-allowed disabled:opacity-80" disabled={loading}>
            {loading ? "Alterando..." : "Alterar senha"}
          </Button>
        </form>
      )}

      {step === "success" && (
        <div className="space-y-6 text-center">
          <p className="text-emerald-300">Senha alterada com sucesso.</p>
          <Button type="button" className="w-full" onClick={() => router.push("/login")}>
            Entrar
          </Button>
        </div>
      )}
    </div>
  );
}
