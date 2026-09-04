import Universe from "@/components/universe/Universe";
import LoginCard from "@/components/auth/LoginCard";
import RecoveryRedeem from "@/components/auth/RecoveryRedeem";

// Força renderização dinâmica — mesmo motivo de app/login/page.tsx e
// app/register/page.tsx (nonce de CSP congelado no build quebraria a
// hidratação, e este componente depende inteiramente dela para trocar o
// token e redirecionar).
export const dynamic = "force-dynamic";

export default async function RecoveryRedeemPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
      <Universe />

      <div className="relative z-10">
        <LoginCard greeting="Bem-vindo de volta." subtitle="Continue de onde parou.">
          <RecoveryRedeem token={token} />
        </LoginCard>
      </div>
    </main>
  );
}
