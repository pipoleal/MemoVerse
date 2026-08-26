// Única fonte de verdade da data/hora oficial de lançamento — lida tanto
// por middleware.ts (decisão de bloqueio, no servidor) quanto por
// ComingSoonView.tsx (contagem regressiva, no cliente). Nunca duplicar
// este valor em outro lugar.
//
// 31/08/2026 18:00 em America/Sao_Paulo = 2026-08-31T21:00:00Z, sempre: o
// Brasil aboliu o horário de verão em 2019, então esse fuso é UTC-3 fixo o
// ano inteiro — esta conversão não depende de nenhuma lib de timezone e
// nunca muda por conta própria (só mudaria se a lei brasileira sobre
// horário de verão mudasse de novo, o que exigiria atualizar este
// comentário e o valor juntos).
export const LAUNCH_AT_UTC_MS = Date.parse("2026-08-31T21:00:00.000Z");

export function isBeforeLaunch(now: number = Date.now()): boolean {
  return now < LAUNCH_AT_UTC_MS;
}
