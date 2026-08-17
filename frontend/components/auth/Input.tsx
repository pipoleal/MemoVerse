import { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
};

export default function Input({
  label,
  className = "",
  ...props
}: InputProps) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-gray-300">
        {label}
      </label>

      <input
        className={`
          w-full rounded-xl
          border border-white/10
          bg-white/5
          px-4 py-3
          text-white
          outline-none
          transition-all
          duration-300
          placeholder:text-gray-500
          focus:border-yellow-400
          focus:bg-white/10
          focus:ring-2
          focus:ring-yellow-400/30
          ${className}
        `}
        {...props}
      />
    </div>
  );
}