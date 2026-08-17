import Universe from "@/components/universe/Universe";
import LoginCard from "@/components/auth/LoginCard";
import LoginForm from "@/components/auth/LoginForm";

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