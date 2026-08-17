"use client";

import type { ReactNode } from "react";

type FieldProps = {
  label: string;
  description?: string;
  children: ReactNode;
};

export default function Field({
  label,
  description,
  children,
}: FieldProps) {
  return (
    <div className="space-y-2">
      <div>
        <label className="block text-sm font-medium text-white">
          {label}
        </label>

        {description && (
          <p className="mt-1 text-sm text-slate-400">
            {description}
          </p>
        )}
      </div>

      {children}
    </div>
  );
}