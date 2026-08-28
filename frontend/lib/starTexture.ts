import * as THREE from "three";

// Textura procedural única de estrela (canvas 2D, nunca uma imagem
// externa): núcleo branco no centro, halo em várias camadas de gradiente
// radial e 4 raios sutis — um único sprite branco com alfa gradual (a cor
// entra depois, multiplicada no shader que a consome). Gerada uma única
// vez (singleton client-only) e compartilhada por qualquer renderização
// de estrela/partícula baseada em THREE.Points que precise da mesma
// linguagem visual — hoje: components/universe/MemoryStars.tsx (Minha
// Galáxia) e experience-view/GalaxyTransition.tsx (Galáxia Viva da
// experiência pública). Extraída de MemoryStars.tsx sem alterar nenhuma
// linha do desenho em si — MemoryStars continua pixel a pixel igual a
// antes desta extração, só passou a importar daqui em vez de definir
// localmente.
let starTextureSingleton: THREE.CanvasTexture | null = null;

export function getStarTexture(): THREE.CanvasTexture {
  if (starTextureSingleton) return starTextureSingleton;

  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    starTextureSingleton = new THREE.CanvasTexture(canvas);
    return starTextureSingleton;
  }

  const cx = size / 2;
  const cy = size / 2;

  // Halo: glow amplo, alfa caindo suavemente até 0 — nada de borda dura.
  const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, size / 2);
  halo.addColorStop(0, "rgba(255,255,255,0.85)");
  halo.addColorStop(0.25, "rgba(255,255,255,0.45)");
  halo.addColorStop(0.55, "rgba(255,255,255,0.16)");
  halo.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = halo;
  ctx.fillRect(0, 0, size, size);

  // Raios sutis (4 pontas) — discretos, nunca um brilho "explosivo".
  ctx.save();
  ctx.translate(cx, cy);
  const rayLength = size * 0.44;
  for (let i = 0; i < 4; i++) {
    ctx.save();
    ctx.rotate((Math.PI / 2) * i);
    const ray = ctx.createLinearGradient(0, 0, 0, -rayLength);
    ray.addColorStop(0, "rgba(255,255,255,0.45)");
    ray.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = ray;
    ctx.fillRect(-1.1, -rayLength, 2.2, rayLength);
    ctx.restore();
  }
  ctx.restore();

  // Núcleo: pequeno e muito brilhante, por cima de tudo o resto.
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, size * 0.15);
  core.addColorStop(0, "rgba(255,255,255,1)");
  core.addColorStop(0.6, "rgba(255,255,255,0.9)");
  core.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(cx, cy, size * 0.15, 0, Math.PI * 2);
  ctx.fill();

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  starTextureSingleton = texture;
  return texture;
}
