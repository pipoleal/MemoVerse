import type { OrnamentKind } from "@/lib/themeRegistry";

import ThemeGlyph, { renderGlyph } from "./ThemeGlyph";

type ThemeOrnamentProps = {
  kind: OrnamentKind;
};

function CherryBlossom({ x, y, size, index }: { x: number; y: number; size: number; index: number }) {
  return (
    <svg x={x - size / 2} y={y - size / 2} width={size} height={size} viewBox="0 0 24 24" overflow="visible">
      <g
        className="mv-flower-blossom"
        style={{ animationDuration: `${4 + index * 0.7}s`, animationDelay: `${-index * 1.3}s` }}
      >
        {renderGlyph("blossom")}
      </g>
    </svg>
  );
}

export default function ThemeOrnament({ kind }: ThemeOrnamentProps) {
  if (kind === "cherry-branch") {
    return (
      <svg
        viewBox="0 0 400 220"
        aria-hidden="true"
        className="mv-flower-branch pointer-events-none absolute -right-4 top-0 w-[72%] max-w-md overflow-visible"
      >
        <path
          d="M8 210C60 150 110 120 170 95s120-40 160-60 70-30 70-30"
          fill="none"
          stroke="#3a1424"
          strokeWidth="7"
          strokeLinecap="round"
        />
        <g className="mv-flower-twig" style={{ transformOrigin: "230px 70px", animationDelay: "-0.8s" }}>
          <path d="M230 70c10-20 30-30 50-30" fill="none" stroke="#3a1424" strokeWidth="4" strokeLinecap="round" />
          <CherryBlossom x={262} y={34} size={26} index={4} />
        </g>
        <g className="mv-flower-twig" style={{ transformOrigin: "343px 28px", animationDelay: "-2.8s" }}>
          <path d="M343 28q-9 13-25 18" fill="none" stroke="#3a1424" strokeWidth="3" strokeLinecap="round" />
          <CherryBlossom x={318} y={46} size={42} index={3} />
        </g>
        {[
          [24, 188, 34],
          [118, 118, 44],
          [212, 78, 54],
        ].map(([x, y, size], index) => (
          <CherryBlossom key={`${x}-${y}`} x={x} y={y} size={size} index={index} />
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
