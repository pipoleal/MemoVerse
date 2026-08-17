"use client";

import { InputHTMLAttributes, useState } from "react";

import Input from "./Input";

type PasswordInputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
};

export default function PasswordInput({
  label,
  ...props
}: PasswordInputProps) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="relative">
      <Input
        {...props}
        label={label}
        type={showPassword ? "text" : "password"}
      />

      <button
        type="button"
        onClick={() => setShowPassword((prev) => !prev)}
        className="absolute right-4 top-10.5 text-sm text-gray-400 transition hover:text-white"
      >
        {showPassword ? "Ocultar" : "Mostrar"}
      </button>
    </div>
  );
}