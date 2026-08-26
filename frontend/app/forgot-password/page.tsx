import ForgotPasswordFlow from "@/components/auth/ForgotPasswordFlow";
import LoginCard from "@/components/auth/LoginCard";
import Universe from "@/components/universe/Universe";

// Força renderização dinâmica — ver comentário em app/login/page.tsx (mesmo
// bug: nonce de CSP congelado no build em páginas estáticas, quebrando a
// hidratação e fazendo o formulário cair em submit GET nativo — era
// exatamente por isso que nenhum e-mail estava sendo enviado: a chamada de
// API nunca acontecia).
export const dynamic = "force-dynamic";

export default function ForgotPasswordPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
      <Universe />
      <div className="relative z-10">
        <LoginCard
          greeting="Recupere sua senha."
          subtitle="Informe seu e-mail para receber um código de recuperação."
        >
          <ForgotPasswordFlow />
        </LoginCard>
      </div>
    </main>
  );
}
