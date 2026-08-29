"use client";

import { useState } from "react";

type AdminConfirmDialogProps = {
  title: string;
  description: string;
  confirmLabel: string;
  // Quando definido, o botão de confirmar só habilita depois do admin
  // digitar exatamente este texto — fricção deliberada para a única ação
  // irreversível do painel (excluir usuário).
  requireText?: string;
  danger?: boolean;
  loading?: boolean;
  errorMessage?: string | null;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function AdminConfirmDialog({
  title,
  description,
  confirmLabel,
  requireText,
  danger = false,
  loading = false,
  errorMessage,
  onConfirm,
  onCancel,
}: AdminConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const canConfirm = !requireText || typed === requireText;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 px-4"
      onClick={onCancel}
      role="presentation"
    >
      <div
        className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-950 p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <h2 className="text-lg font-black text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400">{description}</p>

        {requireText && (
          <div className="mt-4">
            <label className="text-xs text-slate-500">
              Digite <span className="font-mono text-slate-300">{requireText}</span> para confirmar
            </label>
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              autoFocus
              className="mt-1 w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-yellow-400/50"
            />
          </div>
        )}

        {errorMessage && (
          <p className="mt-4 rounded-xl border border-red-400/30 bg-red-400/5 p-3 text-sm text-red-200">
            {errorMessage}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm font-semibold text-slate-200 transition hover:border-white/30"
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={!canConfirm || loading}
            onClick={onConfirm}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40 ${
              danger ? "bg-red-500 text-white hover:bg-red-400" : "bg-yellow-400 text-black hover:scale-105"
            }`}
          >
            {loading ? "Aguarde…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
