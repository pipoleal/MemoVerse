"use client";

import axios from "axios";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { login } from "@/lib/auth";
import { clearPendingExperience, hasPendingExperience, savePendingExperienceDraft } from "@/lib/pendingExperience";

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
      if (hasPendingExperience()) {
        await savePendingExperienceDraft();
        clearPendingExperience();
      }
      router.push("/dashboard");
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
        <span className="text-sm text-white/40" title="Recuperação de senha ainda não está disponível">
          Esqueceu sua senha? Em breve.
        </span>
      </div>
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      <Button type="submit" className="w-full">{loading ? "Entrando..." : "Entrar"}</Button>
    </form>
  );
}
