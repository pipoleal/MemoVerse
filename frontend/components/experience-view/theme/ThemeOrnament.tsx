import type { OrnamentKind } from "@/lib/themeRegistry";

import ThemeGlyph, { renderGlyph } from "./ThemeGlyph";

type ThemeOrnamentProps = {
  kind: OrnamentKind;
};

// Enfeite do canto superior da Abertura (galho de cerejeira no Flores, lua
// na Noite). "none" não renderiza nada — temas sem ornamento próprio ficam
// só com a constelação, que é comum a todos.
export default function ThemeOrnament({ kind }: ThemeOrnamentProps) {
  if (kind === "cherry-branch") {
    return (
      <svg
        viewBox="0 0 400 220"
        aria-hidden="true"
        className="pointer-events-none absolute -right-4 top-0 w-[72%] max-w-md"
      >
        <path
          d="M8 210C60 150 110 120 170 95s120-40 160-60 70-30 70-30"
          fill="none"
          stroke="#3a1424"
          strokeWidth="7"
          strokeLinecap="round"
        />
        <path d="M230 70c10-20 30-30 50-30" fill="none" stroke="#3a1424" strokeWidth="4" strokeLinecap="round" />
        {[
          [24, 188, 34],
          [118, 118, 44],
          [212, 78, 54],
          [318, 46, 42],
          [262, 34, 26],
        ].map(([x, y, size], index) => (
          <svg key={`${x}-${y}`} x={x - size / 2} y={y - size / 2} width={size} height={size} viewBox="0 0 24 24">
            <g
              className="mv-pulse"
              style={{ transformBox: "fill-box", transformOrigin: "center", animationDelay: `${index * 0.6}s` }}
            >
              {renderGlyph("blossom")}
            </g>
          </svg>
        ))}
      </svg>
    );
  }

  if (kind === "crescent-moon") {
    return (
      <div aria-hidden="true" className="pointer-events-none absolute right-10 top-14">
        <ThemeGlyph kind="moon" className="mv-pulse h-20 w-20 drop-shadow-[0_0_30px_var(--mv-accent)]" />
      </div>
    );
  }

  return null;
}
