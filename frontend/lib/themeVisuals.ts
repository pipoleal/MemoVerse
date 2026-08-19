// Visual identity per experience theme (draft.theme). The themes themselves
// are defined in components/experience/steps/StyleStep.tsx (id/icon/title) —
// this module only adds the extra layer StyleStep never needed: a card
// background gradient and an accent color, used by the Dashboard's
// experience cards. Deliberately frontend-only: ExperienceDraft.theme stays
// a free-text CharField in the backend, nothing here is persisted.
export type ThemeVisual = {
  id: string;
  label: string;
  icon: string;
  // Full gradient utility classes (Tailwind v4 bg-linear-*) — written out
  // literally so the build's content scan picks them up.
  gradient: string;
  accent: string;
  glow: string;
};

const THEME_VISUALS: Record<string, ThemeVisual> = {
  universe: {
    id: "universe",
    label: "Universo",
    icon: "🌌",
    gradient: "bg-linear-to-br from-indigo-950 via-purple-900 to-slate-950",
    accent: "text-purple-300 border-purple-400/40",
    glow: "rgba(168,85,247,.35)",
  },
  cinema: {
    id: "cinema",
    label: "Cinema",
    icon: "🎬",
    gradient: "bg-linear-to-br from-neutral-900 via-amber-950 to-black",
    accent: "text-amber-300 border-amber-400/40",
    glow: "rgba(217,119,6,.35)",
  },
  beach: {
    id: "beach",
    label: "Praia",
    icon: "🌊",
    gradient: "bg-linear-to-br from-sky-900 via-cyan-800 to-orange-300/30",
    accent: "text-cyan-200 border-cyan-400/40",
    glow: "rgba(34,211,238,.3)",
  },
  flowers: {
    id: "flowers",
    label: "Flores",
    icon: "🌸",
    gradient: "bg-linear-to-br from-rose-950 via-pink-800 to-fuchsia-900",
    accent: "text-pink-200 border-pink-400/40",
    glow: "rgba(244,114,182,.3)",
  },
  night: {
    id: "night",
    label: "Noite",
    icon: "🌙",
    gradient: "bg-linear-to-br from-slate-950 via-blue-950 to-indigo-950",
    accent: "text-blue-200 border-blue-400/40",
    glow: "rgba(96,165,250,.3)",
  },
  minimal: {
    id: "minimal",
    label: "Minimalista",
    icon: "🤍",
    gradient: "bg-linear-to-br from-slate-800 via-slate-900 to-slate-950",
    accent: "text-slate-200 border-white/30",
    glow: "rgba(226,232,240,.2)",
  },
};

// Unknown/empty theme (e.g. a draft still early in the wizard) falls back to
// the same neutral visual as "minimal" — never a hard error, never invented
// data beyond the id the user actually picked.
export function getThemeVisual(themeId: string): ThemeVisual {
  return THEME_VISUALS[themeId] ?? THEME_VISUALS.minimal;
}
