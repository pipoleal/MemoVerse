import { renderGlyph } from "./ThemeGlyph";

// Planeta da tela Começar — SVG puro (sem WebGL), colorido só pelas
// variáveis do tema (--mv-planet-light/--mv-planet-dark): rosa no Flores,
// roxo no Universo, e assim por diante. Grade de meridianos/paralelos,
// anel orbital inclinado, marcador luminoso pulsando e um brilho no anel.
const MERIDIANS = [30, 70, 110, 145, 175];
const PARALLELS = [-140, -100, -55, 0, 55, 100, 140];

export default function ThemePlanet() {
  return (
    <svg viewBox="-260 -230 520 460" aria-hidden="true" className="h-auto w-full overflow-visible">
      <defs>
        <radialGradient id="mv-planet-fill" cx="30%" cy="28%" r="80%">
          <stop offset="0%" style={{ stopColor: "var(--mv-planet-light)" }} />
          <stop offset="55%" style={{ stopColor: "color-mix(in srgb, var(--mv-planet-light) 45%, var(--mv-planet-dark))" }} />
          <stop offset="100%" style={{ stopColor: "var(--mv-planet-dark)" }} />
        </radialGradient>
        <radialGradient id="mv-planet-halo" r="50%">
          <stop offset="60%" style={{ stopColor: "var(--mv-planet-light)", stopOpacity: 0.28 }} />
          <stop offset="100%" style={{ stopColor: "var(--mv-planet-light)", stopOpacity: 0 }} />
        </radialGradient>
        <clipPath id="mv-planet-clip">
          <circle r="180" />
        </clipPath>
      </defs>

      <circle r="250" fill="url(#mv-planet-halo)" />
      <circle r="198" fill="none" stroke="var(--mv-accent-soft)" strokeOpacity="0.12" />
      <circle r="212" fill="none" stroke="var(--mv-accent-soft)" strokeOpacity="0.07" />

      <circle r="180" fill="url(#mv-planet-fill)" />

      <g clipPath="url(#mv-planet-clip)" fill="none" stroke="#fff" strokeOpacity="0.14" strokeWidth="1">
        <line x1="0" y1="-180" x2="0" y2="180" />
        {MERIDIANS.map((rx) => (
          <ellipse key={rx} rx={rx} ry="180" />
        ))}
        {PARALLELS.map((y) => (
          <ellipse key={y} cx="0" cy={y} rx={Math.sqrt(180 * 180 - y * y)} ry="10" />
        ))}
      </g>

      <circle r="180" fill="none" stroke="var(--mv-accent)" strokeOpacity="0.6" strokeWidth="2.5" />

      <ellipse rx="250" ry="70" fill="none" stroke="var(--mv-accent-soft)" strokeOpacity="0.4" strokeWidth="1.4" transform="rotate(16)" />

      {/* Brilho sobre o anel (lado esquerdo). */}
      <svg x="-226" y="-140" width="34" height="34" viewBox="0 0 24 24" className="overflow-visible">
        <g className="mv-pulse" style={{ transformBox: "fill-box", transformOrigin: "center" }}>
          {renderGlyph("sparkle")}
        </g>
      </svg>

      {/* Marcador luminoso — "aqui começa a sua história". */}
      <g transform="translate(70 -40)">
        <circle r="34" fill="none" stroke="#fff" strokeOpacity="0.35" />
        <circle
          r="22"
          fill="none"
          stroke="#fff"
          strokeOpacity="0.6"
          className="mv-pulse"
          style={{ transformBox: "fill-box", transformOrigin: "center" }}
        />
        <circle r="9" fill="#fff" />
      </g>
    </svg>
  );
}
