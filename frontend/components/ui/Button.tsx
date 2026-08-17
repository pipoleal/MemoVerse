import { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
};

export default function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonProps) {
  const base =
    "group relative overflow-hidden rounded-full px-8 py-4 font-semibold transition-all duration-300 ease-out";

  const variants = {
    primary:
      "bg-yellow-400 text-black hover:scale-105 hover:-translate-y-1 hover:shadow-[0_0_40px_rgba(250,204,21,.55)]",

    secondary:
      "border border-white text-white hover:bg-white hover:text-black hover:scale-105 hover:-translate-y-1",
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}