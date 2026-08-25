// Formato canônico de uma "estrela" que representa uma memória real (uma
// experiência publicada) dentro da Universe Engine — consumido pela Minha
// Galáxia e pela Galáxia Viva (Fases 2+). Os consumidores decorativos
// atuais de Universe.tsx (landing/login/register/dashboard) nunca passam
// isto: continuam renderizando só o fundo de estrelas genérico.
//
// Não existe tipo equivalente reaproveitável no projeto hoje:
// lib/star-generator.ts exporta um `Star` 2D (top/left em %, pensado para
// CSS puro) e experience-view/StarField.tsx tem seu próprio `StarData`
// privado (não exportado), também 2D/DOM, para uma animação de fases
// distinta (idle/transition/burst/converge). Nenhum dos dois carrega
// posição 3D, cor por estrela ou identidade de uma experiência — por isso
// este é um tipo novo, não uma duplicata de algo existente.
export type StarData = {
  id: string;
  position: [number, number, number];
  size: number;
  color: string;
  glow?: string;
  label?: string;
  metadata?: unknown;
};
