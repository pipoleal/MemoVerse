"use client";

import type { TextareaHTMLAttributes } from "react";

export default function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={`
        w-full
        resize-none
        rounded-2xl
        border
        border-white/10
        bg-white/5
        px-5
        py-4
        text-white
        outline-none
        placeholder:text-slate-500
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