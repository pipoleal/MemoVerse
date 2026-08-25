// Checagem mínima de suporte a WebGL — só client-side (usa document/window),
// nunca chamado durante SSR. Usada pela Minha Galáxia (Fase 2) para decidir
// entre montar a UniverseEngine ou cair direto no fallback em lista, sem
// esperar um erro de renderização acontecer primeiro. A Galáxia Viva (Fase
// 4) deve reaproveitar esta mesma função em vez de duplicá-la.
export function isWebGLAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      window.WebGLRenderingContext &&
      (canvas.getContext("webgl") || canvas.getContext("experimental-webgl"))
    );
  } catch {
    return false;
  }
}
