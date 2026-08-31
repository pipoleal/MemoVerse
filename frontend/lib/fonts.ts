import { Cormorant_Garamond } from "next/font/google";

// Fonte serifada usada nos títulos "editoriais" da landing page (itálico
// para headlines emocionais, versalete para a nova seção de ocasiões) —
// mesma família já carregada por components/universe/GalaxiaViva.tsx
// (--gv-font-cormorant), só centralizada aqui para não repetir a mesma
// chamada a next/font/google em cada componente novo da landing. Nunca
// aplicada fora da landing: o resto do produto continua em Geist Sans.
export const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  style: ["normal", "italic"],
  display: "swap",
});
