"use client";

import axios from "axios";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { login } from "@/lib/auth";
import { clearPendingExperience, hasPendingExperience, savePendingExperienceDraft } from "@/lib/pendingExperience";
import { saveUserFirstName } from "@/lib/storage";
import Button from "../ui/Button";
import Input from "./Input";
import PasswordInput from "./PasswordInput";

function errorMessage(error: unknown) {
  if (!axios.isAxiosError(error)) return "Não foi possível concluir o cadastro. Tente novamente.";
  if (!error.response) return "Não foi possível conectar ao servidor. Verifique se o backend está em execução e tente novamente.";
  const data = error.response?.data;
  if (typeof data?.email?.[0] === "string") return data.email[0];
  if (typeof data?.password?.[0] === "string") return data.password[0];
  return "Não foi possível concluir o cadastro. Verifique seus dados e tente novamente.";
}

export default function RegisterForm() {
  const router = useRouter();
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [registrationComplete, setRegistrationComplete] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (!registrationComplete) {
        await api.post("/auth/register/", { first_name: firstName, last_name: lastName, email, password });
        setRegistrationComplete(true);
      }
      await login({ email, password });
      saveUserFirstName(firstName);
      if (hasPendingExperience()) {
        await savePendingExperienceDraft();
        clearPendingExperience();
      }
      router.push("/dashboard");
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <Input label="Nome" name="firstName" value={firstName} onChange={(event) => setFirstName(event.target.value)} required />
      <Input label="Sobrenome" name="lastName" value={lastName} onChange={(event) => setLastName(event.target.value)} required />
      <Input label="E-mail" type="email" name="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
      <PasswordInput label="Senha" name="password" placeholder="Mínimo de 8 caracteres" value={password} onChange={(event) => setPassword(event.target.value)} required />
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      <Button type="submit" className="w-full">{loading ? "Criando conta..." : "Criar conta"}</Button>
    </form>
  );
}
