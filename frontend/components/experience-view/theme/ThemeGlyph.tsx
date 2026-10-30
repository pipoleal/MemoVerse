import type { GlyphKind } from "@/lib/themeRegistry";

type ThemeGlyphProps = {
  kind: GlyphKind;
  className?: string;
};

// Pequenos ícones do tema (selo da carta, centro do divisor, fechamento da
// mensagem). Sempre decorativos — aria-hidden — e coloridos só pelas
// variáveis --mv-* do tema, nunca por uma cor fixa.
export default function ThemeGlyph({ kind, className = "h-4 w-4" }: ThemeGlyphProps) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" className={className}>
      {renderGlyph(kind)}
    </svg>
  );
}

// Exportado para quem precisa do glifo dentro de um <svg> maior (galho de
// ThemeOrnament), sem um <svg> próprio em volta.
export function renderGlyph(kind: GlyphKind) {
  switch (kind) {
    case "heart":
      return (
        <path
          d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2Z"
          fill="var(--mv-accent)"
        />
      );

    case "blossom":
      return (
        <g>
          {[0, 72, 144, 216, 288].map((angle) => (
            <ellipse
              key={angle}
              cx="12"
              cy="6.6"
              rx="3.6"
              ry="4.6"
              fill="var(--mv-accent-soft)"
              stroke="var(--mv-accent)"
              strokeWidth="0.8"
              transform={`rotate(${angle} 12 12)`}
            />
          ))}
          <circle cx="12" cy="12" r="2.1" fill="var(--mv-gold)" />
        </g>
      );

    case "star":
      return (
        <path
          d="m12 3 2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6-4.5-4.2 6.1-.7L12 3Z"
          fill="var(--mv-accent)"
        />
      );

    case "sparkle":
      return <path d="M12 2c.6 5.4 4.6 9.4 10 10-5.4.6-9.4 4.6-10 10-.6-5.4-4.6-9.4-10-10 5.4-.6 9.4-4.6 10-10Z" fill="var(--mv-gold)" />;

    case "clapper":
      return (
        <g fill="var(--mv-accent)">
          <path d="M3 10h18v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9Z" />
          <path d="m3.2 8.6 16.4-4.4.8 3-16.4 4.4-.8-3Z" opacity="0.8" />
        </g>
      );

    case "shell":
      return (
        <g>
          <path d="M12 3c5 0 9 4.4 9 9.6 0 2-1 3.4-2.4 4.4L12 21l-6.6-4c-1.4-1-2.4-2.4-2.4-4.4C3 7.4 7 3 12 3Z" fill="var(--mv-accent)" />
          <path d="M12 21V4M12 21 6 6M12 21l6-15M12 21 3.6 10M12 21l8.4-11" stroke="var(--mv-night)" strokeOpacity="0.35" strokeWidth="0.9" fill="none" />
        </g>
      );

    case "moon":
      return <path d="M15.5 3.2A8.8 8.8 0 1 0 20.8 15 7.2 7.2 0 0 1 15.5 3.2Z" fill="var(--mv-accent)" />;

    case "dot":
      return <circle cx="12" cy="12" r="4" fill="var(--mv-accent)" />;
  }
}
