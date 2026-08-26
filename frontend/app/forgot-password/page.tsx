import ForgotPasswordFlow from "@/components/auth/ForgotPasswordFlow";
import LoginCard from "@/components/auth/LoginCard";
import Universe from "@/components/universe/Universe";

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
