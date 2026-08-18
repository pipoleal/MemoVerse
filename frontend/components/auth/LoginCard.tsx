import { ReactNode } from "react";

type LoginCardProps = {
  children: ReactNode;
  greeting?: string;
  subtitle?: string;
};

export default function LoginCard({
  children,
  greeting = "Bem-vindo de volta.",
  subtitle = "Entre para acessar suas experiências.",
}: LoginCardProps) {
  return (
    <div
      className="
        w-full
        max-w-md
        rounded-3xl
        border
        border-white/10
        bg-white/5
        p-10
        shadow-2xl
        backdrop-blur-xl
      "
    >
      <div className="mb-8 text-center">
        <h1 className="bg-linear-to-r from-white via-slate-200 to-yellow-300 bg-clip-text text-4xl font-bold text-transparent">
          MemoVerse
        </h1>

        <p className="mt-3 text-gray-300">
          {greeting}
        </p>

        <p className="mt-1 text-sm text-gray-400">
          {subtitle}
        </p>
      </div>

      {children}
    </div>
  );
}