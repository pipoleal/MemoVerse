import { getThemeVisual } from "@/lib/themeVisuals";

// The visual "header" block of an experience card — isolated so the same
// theme treatment can be reused wherever else a memory needs to be
// represented visually (e.g. a future Minha Galáxia view), without
// duplicating the gradient-per-theme logic.
export default function ThemeVisual({ theme }: { theme: string }) {
  const visual = getThemeVisual(theme);

  return (
    <div className={`relative flex h-32 items-center justify-center overflow-hidden rounded-2xl ${visual.gradient}`}>
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.18),transparent_65%)]" />
      <span className="text-5xl drop-shadow-lg">{visual.icon}</span>
    </div>
  );
}
