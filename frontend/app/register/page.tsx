import RegisterForm from "@/components/auth/RegisterForm";
import LoginCard from "@/components/auth/LoginCard";
import Universe from "@/components/universe/Universe";

export default function RegisterPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950">
      <Universe />
      <div className="relative z-10"><LoginCard><RegisterForm /></LoginCard></div>
    </main>
  );
}
