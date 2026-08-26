import Universe from "@/components/universe/Universe";
import LoginCard from "@/components/auth/LoginCard";
import LoginForm from "@/components/auth/LoginForm";

// Força renderização dinâmica (SSR por requisição). Sem isso, esta página é
// prerenderizada estaticamente e o nonce de CSP embutido nos scripts de
// bootstrap do Next.js (self.__next_f...) fica congelado no valor do
// momento do build, nunca batendo com o nonce por requisição que o
// middleware gera de verdade — o navegador bloqueia esses scripts por CSP,
// a hidratação nunca completa, e o formulário cai no comportamento padrão
// do HTML (submit GET, recarregando a página com email/senha na própria
// URL, em vez de chamar a API). Confirmado ao vivo em produção: o clique
// em "Entrar" resultava em "/login?email=...&password=..." na barra de
// endereço, sem nenhuma chamada de API — mesmo bug já corrigido antes em
// app/coming-soon/page.tsx.
export const dynamic = "force-dynamic";

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
      <Universe />

      <div className="relative z-10">
        <LoginCard>
          <LoginForm />
        </LoginCard>
      </div>
    </main>
  );
}