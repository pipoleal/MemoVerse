import RegisterForm from "@/components/auth/RegisterForm";
import LoginCard from "@/components/auth/LoginCard";
import Universe from "@/components/universe/Universe";

// Força renderização dinâmica — ver comentário em app/login/page.tsx (mesmo
// bug: nonce de CSP congelado no build em páginas estáticas, quebrando a
// hidratação e fazendo o formulário cair em submit GET nativo).
export const dynamic = "force-dynamic";

export default function RegisterPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
      <Universe />
      <div className="relative z-10">
        <LoginCard
          greeting="Crie sua conta."
          subtitle="Comece a transformar suas memórias em experiências inesquecíveis."
        >
          <RegisterForm />
        </LoginCard>
      </div>
    </main>
  );
}
