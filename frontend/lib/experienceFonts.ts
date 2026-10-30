import { Cormorant_Garamond } from "next/font/google";

// Serifa da experiência pública (nome do destinatário, carta, legendas) —
// a mesma em todos os temas. Exposta só como variável CSS
// (--font-mv-serif), aplicada na raiz do ExperienceViewer e lida pela
// classe `.mv-serif` de app/globals.css; o resto do produto continua em
// Geist. Os rótulos em caixa alta usam a própria Geist (font-sans).
export const experienceSerif = Cormorant_Garamond({
  variable: "--font-mv-serif",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});
