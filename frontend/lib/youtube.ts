// Extração/validação de video id do YouTube — espelha byte a byte
// backend/app/apps/experiences/youtube.py (mesmos hosts, mesmos formatos de
// path, mesmo regex de id) para que cliente e servidor nunca discordem
// sobre o que é um link válido. Única fonte de verdade usada tanto pela
// etapa 7 do wizard (validação/feedback imediato do link colado, ver
// steps/MusicStep.tsx) quanto pelo player em components/universe/
// GalaxiaViva.tsx (deriva o videoId a tocar) — nunca duas regex divergentes
// para a mesma coisa.

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "youtu.be",
  "www.youtu.be",
]);

// Formato real de video id do YouTube: sempre 11 caracteres.
const VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

// null quando `url` não é um link de vídeo do YouTube reconhecível. Aceita
// watch?v=, youtu.be/ e shorts/, com quaisquer parâmetros extras (t=,
// list=, si=, etc.) — esses são ignorados, só o id importa.
export function extractYouTubeVideoId(url: string): string | null {
  if (!url) return null;

  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return null;
  }

  const hostname = parsed.hostname.toLowerCase();
  if (!YOUTUBE_HOSTS.has(hostname)) {
    return null;
  }

  if (hostname === "youtu.be" || hostname === "www.youtu.be") {
    const candidate = parsed.pathname.replace(/^\//, "").split("/")[0];
    return VIDEO_ID_PATTERN.test(candidate) ? candidate : null;
  }

  if (parsed.pathname === "/watch") {
    const candidate = parsed.searchParams.get("v");
    return candidate && VIDEO_ID_PATTERN.test(candidate) ? candidate : null;
  }

  const shortsMatch = parsed.pathname.match(/^\/shorts\/([^/]+)\/?$/);
  if (shortsMatch) {
    const candidate = shortsMatch[1];
    return VIDEO_ID_PATTERN.test(candidate) ? candidate : null;
  }

  return null;
}

export function isValidYouTubeUrl(url: string): boolean {
  return extractYouTubeVideoId(url) !== null;
}
