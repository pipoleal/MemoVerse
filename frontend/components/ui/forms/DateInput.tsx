"use client";

import type { InputHTMLAttributes } from "react";

export default function DateInput({
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      type="date"
      className={`
        w-full
        rounded-2xl
        border
        border-white/10
        bg-white/5
        px-5
        py-4
        text-white
        outline-none
        backdrop-blur-xl
        transition-all
        duration-300
        focus:border-yellow-400
        focus:bg-white/10
        focus:ring-2
        focus:ring-yellow-400/20
        ${className}
      `}
    />
  );
}