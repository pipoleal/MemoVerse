const KEY = "memoverse.pending-galaxy-save";

export type StoredGalaxySave = {
  slug: string;
};

function isBrowser() {
  return typeof window !== "undefined";
}

// localStorage (not sessionStorage): same reasoning as
// anonymousDraft.ts — must survive the same-tab navigation to
// /register or /login, and a closed/reopened tab before auth finishes.
export function savePendingGalaxySave(slug: string) {
  if (!isBrowser()) return;
  try {
    localStorage.setItem(KEY, JSON.stringify({ slug } satisfies StoredGalaxySave));
  } catch {
    // Storage unavailable (private mode, quota) — degrades to "no
    // resume", never breaks the "Criar minha conta"/"Entrar" navigation
    // itself.
  }
}

export function getPendingGalaxySave(): StoredGalaxySave | null {
  if (!isBrowser()) return null;
  try {
    const stored = localStorage.getItem(KEY);
    if (!stored) return null;
    const parsed = JSON.parse(stored) as Partial<StoredGalaxySave>;
    if (typeof parsed.slug !== "string") {
      localStorage.removeItem(KEY);
      return null;
    }
    return { slug: parsed.slug };
  } catch {
    return null;
  }
}

export function clearPendingGalaxySave() {
  if (!isBrowser()) return;
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignored on purpose, same pattern as the rest of local storage here
  }
}
