"use client";

import { useEffect, useState } from "react";

// setDebounced só é chamado dentro do callback do setTimeout (nunca
// síncrono no corpo do efeito) — mesmo motivo pelo qual os outros hooks
// deste diretório nunca chamam setState direto no corpo do useEffect.
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
