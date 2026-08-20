// Single source of visual implementation for every experience theme —
// replaces the three previously-duplicated dictionaries (StyleStep's own
// `styles` list, lib/themeVisuals.ts, experience-view/scenes/letter-theme.ts).
// The backend (apps.experiences.models.Theme, GET /api/experiences/themes/)
// is the source of truth for WHICH theme codes exist, their display name,
// and whether they're active/ordered — this registry only ever answers
// "given a code, how does it look": icon, palette, typography, and the
// per-surface classes each part of the product already needed.
//
// ExperienceDraft.theme stays a free-text string in the backend (see the
// comment on that field) — a code with no entry here (a legacy/unknown
// value) always resolves through getThemeVisual()'s fallback below rather
// than crashing or rendering unstyled.
export type ThemeVisual = {
  code: string;
  // Fallback label only — when the live catalog from GET
  // /api/experiences/themes/ is available (e.g. StyleStep), its `name` is
  // the authoritative one to display. This is used wherever only a raw
  // theme code is available with no accompanying catalog fetch (the
  // Dashboard's ExperienceCard, or a legacy/unknown code).
  name: string;
  icon: string;
  description: string;
  // Shared palette — drives both the Dashboard's experience card (gradient
  // background + icon) and the background of every chapter of the public
  // experience (ExperienceViewer and its chapters).
  gradient: string;
  accent: string;
  glow: string;
  // "font-serif" | "font-sans" — reused wherever a chapter renders a
  // prominent heading (RecipientRevealChapter today; LetterChapter already
  // carries its own font choice inside `letter.textClass`).
  headingFontClass: string;
  // Hex color for the closing chapter's WebGL <color attach="background">
  // (GalaxyChapter) — a Canvas paints an opaque background of its own, so
  // the CSS `gradient` above never shows through it; this is the one place
  // that needs a raw color instead of a Tailwind class.
  canvasBackground: string;
  // Everything LetterChapter needs — unchanged shape from the previous
  // letter-theme.ts, just relocated here.
  letter: {
    backdropClass: string;
    cardClass: string;
    primaryClass: string;
    secondaryClass: string;
    textClass: string;
    ornamentClass: string;
    glowClass: string;
    entryClass: string;
  };
};

export const DEFAULT_THEME_CODE = "universe";

export const THEME_REGISTRY: Record<string, ThemeVisual> = {
  universe: {
    code: "universe",
    name: "Universo",
    icon: "🌌",
    description: "Uma experiência cercada por estrelas e memórias.",
    gradient: "bg-linear-to-br from-indigo-950 via-purple-900 to-slate-950",
    accent: "text-purple-300 border-purple-400/40",
    glow: "rgba(168,85,247,.35)",
    headingFontClass: "font-serif",
    canvasBackground: "#0b0620",
    letter: {
      backdropClass: "bg-[radial-gradient(circle_at_top,#1e1b4b_0%,#080b1e_45%,#02030a_100%)]",
      cardClass: "border-indigo-200/20 bg-slate-950/55",
      primaryClass: "text-indigo-100",
      secondaryClass: "text-indigo-200/65",
      textClass: "font-serif text-slate-100/90",
      ornamentClass: "border-indigo-200/25 bg-indigo-200/10",
      glowClass: "bg-indigo-400/20",
      entryClass: "translate-y-8",
    },
  },
  cinema: {
    code: "cinema",
    name: "Cinema",
    icon: "🎬",
    description: "Transforme sua história em uma experiência cinematográfica.",
    gradient: "bg-linear-to-br from-neutral-900 via-amber-950 to-black",
    accent: "text-amber-300 border-amber-400/40",
    glow: "rgba(217,119,6,.35)",
    headingFontClass: "font-serif",
    canvasBackground: "#0a0705",
    letter: {
      backdropClass: "bg-[radial-gradient(circle_at_top,#3d260d_0%,#120d08_46%,#030303_100%)]",
      cardClass: "border-amber-200/20 bg-stone-950/65",
      primaryClass: "text-amber-100",
      secondaryClass: "text-amber-200/60",
      textClass: "font-serif text-stone-100/90",
      ornamentClass: "border-amber-200/30 bg-amber-200/10",
      glowClass: "bg-amber-300/20",
      entryClass: "translate-y-10 scale-[0.98]",
    },
  },
  beach: {
    code: "beach",
    name: "Praia",
    icon: "🌊",
    description: "Uma atmosfera leve, romântica e cheia de lembranças.",
    gradient: "bg-linear-to-br from-sky-900 via-cyan-800 to-orange-300/30",
    accent: "text-cyan-200 border-cyan-400/40",
    glow: "rgba(34,211,238,.3)",
    headingFontClass: "font-serif",
    canvasBackground: "#041c24",
    letter: {
      backdropClass: "bg-[radial-gradient(circle_at_top,#164e63_0%,#0c2e42_44%,#03131d_100%)]",
      cardClass: "border-cyan-100/20 bg-slate-950/55",
      primaryClass: "text-cyan-50",
      secondaryClass: "text-cyan-100/65",
      textClass: "font-serif text-slate-50/90",
      ornamentClass: "border-cyan-100/25 bg-cyan-100/10",
      glowClass: "bg-cyan-300/20",
      entryClass: "translate-y-7",
    },
  },
  flowers: {
    code: "flowers",
    name: "Flores",
    icon: "🌸",
    description: "Uma experiência delicada para histórias especiais.",
    gradient: "bg-linear-to-br from-rose-950 via-pink-800 to-fuchsia-900",
    accent: "text-pink-200 border-pink-400/40",
    glow: "rgba(244,114,182,.3)",
    headingFontClass: "font-serif",
    canvasBackground: "#1a0512",
    letter: {
      backdropClass: "bg-[radial-gradient(circle_at_top,#571b3b_0%,#2a1021_44%,#10040b_100%)]",
      cardClass: "border-rose-100/20 bg-rose-950/35",
      primaryClass: "text-rose-50",
      secondaryClass: "text-rose-100/65",
      textClass: "font-serif text-rose-50/90",
      ornamentClass: "border-rose-100/25 bg-rose-100/10",
      glowClass: "bg-rose-300/20",
      entryClass: "translate-y-8 scale-[0.99]",
    },
  },
  night: {
    code: "night",
    name: "Noite",
    icon: "🌙",
    description: "Uma atmosfera elegante para momentos inesquecíveis.",
    gradient: "bg-linear-to-br from-slate-950 via-blue-950 to-indigo-950",
    accent: "text-blue-200 border-blue-400/40",
    glow: "rgba(96,165,250,.3)",
    headingFontClass: "font-serif",
    canvasBackground: "#050814",
    letter: {
      backdropClass: "bg-[radial-gradient(circle_at_top,#1e293b_0%,#0b1020_45%,#02040a_100%)]",
      cardClass: "border-slate-200/20 bg-slate-950/60",
      primaryClass: "text-slate-100",
      secondaryClass: "text-slate-300/65",
      textClass: "font-serif text-slate-100/90",
      ornamentClass: "border-slate-200/25 bg-slate-200/10",
      glowClass: "bg-slate-300/15",
      entryClass: "translate-y-9",
    },
  },
  minimal: {
    code: "minimal",
    name: "Minimalista",
    icon: "🤍",
    description: "Uma experiência simples, elegante e emocional.",
    gradient: "bg-linear-to-br from-slate-800 via-slate-900 to-slate-950",
    accent: "text-slate-200 border-white/30",
    glow: "rgba(226,232,240,.2)",
    headingFontClass: "font-sans",
    canvasBackground: "#0a0a0c",
    letter: {
      backdropClass: "bg-[radial-gradient(circle_at_top,#262626_0%,#111111_48%,#030303_100%)]",
      cardClass: "border-white/15 bg-white/5",
      primaryClass: "text-white",
      secondaryClass: "text-white/55",
      textClass: "font-sans text-white/85",
      ornamentClass: "border-white/15 bg-white/5",
      glowClass: "bg-white/10",
      entryClass: "translate-y-6",
    },
  },
};

// Unknown/legacy/empty code (a draft mid-wizard, or an old value no longer
// in the active catalog) never errors and never renders unstyled — always
// resolves to a real, complete visual definition.
export function getThemeVisual(code?: string | null): ThemeVisual {
  if (code && THEME_REGISTRY[code]) return THEME_REGISTRY[code];
  return THEME_REGISTRY[DEFAULT_THEME_CODE];
}
