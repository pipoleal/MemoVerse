export type LetterThemePreset = {
  backdropClass: string;
  cardClass: string;
  primaryClass: string;
  secondaryClass: string;
  textClass: string;
  ornamentClass: string;
  glowClass: string;
  entryClass: string;
};

export const LETTER_THEMES: Record<string, LetterThemePreset> = {
  universe: {
    backdropClass: "bg-[radial-gradient(circle_at_top,#1e1b4b_0%,#080b1e_45%,#02030a_100%)]",
    cardClass: "border-indigo-200/20 bg-slate-950/55",
    primaryClass: "text-indigo-100",
    secondaryClass: "text-indigo-200/65",
    textClass: "font-serif text-slate-100/90",
    ornamentClass: "border-indigo-200/25 bg-indigo-200/10",
    glowClass: "bg-indigo-400/20",
    entryClass: "translate-y-8",
  },
  cinema: {
    backdropClass: "bg-[radial-gradient(circle_at_top,#3d260d_0%,#120d08_46%,#030303_100%)]",
    cardClass: "border-amber-200/20 bg-stone-950/65",
    primaryClass: "text-amber-100",
    secondaryClass: "text-amber-200/60",
    textClass: "font-serif text-stone-100/90",
    ornamentClass: "border-amber-200/30 bg-amber-200/10",
    glowClass: "bg-amber-300/20",
    entryClass: "translate-y-10 scale-[0.98]",
  },
  beach: {
    backdropClass: "bg-[radial-gradient(circle_at_top,#164e63_0%,#0c2e42_44%,#03131d_100%)]",
    cardClass: "border-cyan-100/20 bg-slate-950/55",
    primaryClass: "text-cyan-50",
    secondaryClass: "text-cyan-100/65",
    textClass: "font-serif text-slate-50/90",
    ornamentClass: "border-cyan-100/25 bg-cyan-100/10",
    glowClass: "bg-cyan-300/20",
    entryClass: "translate-y-7",
  },
  flowers: {
    backdropClass: "bg-[radial-gradient(circle_at_top,#571b3b_0%,#2a1021_44%,#10040b_100%)]",
    cardClass: "border-rose-100/20 bg-rose-950/35",
    primaryClass: "text-rose-50",
    secondaryClass: "text-rose-100/65",
    textClass: "font-serif text-rose-50/90",
    ornamentClass: "border-rose-100/25 bg-rose-100/10",
    glowClass: "bg-rose-300/20",
    entryClass: "translate-y-8 scale-[0.99]",
  },
  night: {
    backdropClass: "bg-[radial-gradient(circle_at_top,#1e293b_0%,#0b1020_45%,#02040a_100%)]",
    cardClass: "border-slate-200/20 bg-slate-950/60",
    primaryClass: "text-slate-100",
    secondaryClass: "text-slate-300/65",
    textClass: "font-serif text-slate-100/90",
    ornamentClass: "border-slate-200/25 bg-slate-200/10",
    glowClass: "bg-slate-300/15",
    entryClass: "translate-y-9",
  },
  minimal: {
    backdropClass: "bg-[radial-gradient(circle_at_top,#262626_0%,#111111_48%,#030303_100%)]",
    cardClass: "border-white/15 bg-white/5",
    primaryClass: "text-white",
    secondaryClass: "text-white/55",
    textClass: "font-sans text-white/85",
    ornamentClass: "border-white/15 bg-white/5",
    glowClass: "bg-white/10",
    entryClass: "translate-y-6",
  },
};

export function getLetterTheme(
  theme: string
): LetterThemePreset {
  return LETTER_THEMES[theme] ?? LETTER_THEMES.universe;
}
