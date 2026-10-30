"use client";

import { useEffect, useRef } from "react";

import type { ParticleKind } from "@/lib/themeRegistry";

type ThemeParticlesProps = {
  kind: ParticleKind;
};

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  rotation: number;
  spin: number;
  phase: number;
  alpha: number;
};

// Camada ambiente do tema (pétalas caindo no Flores, vaga-lumes na Noite...)
// — um único <canvas> 2D fixo por cima da experiência, nunca DOM por
// partícula. Barato de propósito, porque a maioria abre no celular:
// poucas partículas (menos ainda em tela pequena), devicePixelRatio
// limitado a 2, loop parado com a aba em segundo plano e nenhum quadro
// desenhado com prefers-reduced-motion.
const COUNTS: Record<ParticleKind, [mobile: number, desktop: number]> = {
  petals: [14, 24],
  "shooting-stars": [2, 3],
  "projector-dust": [26, 44],
  "sun-glints": [14, 24],
  fireflies: [12, 20],
  dots: [10, 16],
};

export default function ThemeParticles({ kind }: ThemeParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const styles = getComputedStyle(canvas);
    const accent = styles.getPropertyValue("--mv-accent").trim() || "#ffffff";
    const accentSoft = styles.getPropertyValue("--mv-accent-soft").trim() || "#ffffff";
    const gold = styles.getPropertyValue("--mv-gold").trim() || "#ffd76a";

    let width = 0;
    let height = 0;
    let particles: Particle[] = [];
    let frame = 0;
    let last = performance.now();

    function spawn(initial: boolean): Particle {
      const base: Particle = {
        x: Math.random() * width,
        y: Math.random() * height,
        vx: 0,
        vy: 0,
        size: 1,
        rotation: Math.random() * Math.PI * 2,
        spin: (Math.random() - 0.5) * 0.6,
        phase: Math.random() * Math.PI * 2,
        alpha: 0.25 + Math.random() * 0.35,
      };

      switch (kind) {
        case "petals":
          return {
            ...base,
            y: initial ? base.y : -20,
            vx: 4 + Math.random() * 10,
            vy: 14 + Math.random() * 18,
            size: 3 + Math.random() * 4,
          };
        case "shooting-stars":
          return {
            ...base,
            x: Math.random() * width * 0.8,
            y: Math.random() * height * 0.45,
            vx: 420 + Math.random() * 220,
            vy: 160 + Math.random() * 90,
            size: 60 + Math.random() * 60,
            // Espera antes de cruzar a tela (fase < 0 = invisível).
            phase: initial ? -Math.random() * 6 : -(3 + Math.random() * 6),
            alpha: 0.8,
          };
        case "projector-dust":
          return { ...base, vx: (Math.random() - 0.5) * 8, vy: (Math.random() - 0.5) * 8, size: 0.6 + Math.random() * 1.4 };
        case "sun-glints":
          return { ...base, vy: -(3 + Math.random() * 5), size: 2 + Math.random() * 3 };
        case "fireflies":
          return { ...base, vx: (Math.random() - 0.5) * 14, vy: (Math.random() - 0.5) * 14, size: 1.4 + Math.random() * 1.6 };
        case "dots":
          return { ...base, size: 0.8 + Math.random() * 1.2 };
      }
    }

    function resize() {
      if (!canvas || !context) return;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);

      const [mobile, desktop] = COUNTS[kind];
      const count = width < 640 ? mobile : desktop;
      particles = Array.from({ length: count }, () => spawn(true));
    }

    function step(p: Particle, dt: number, time: number) {
      switch (kind) {
        case "petals":
          p.x += (p.vx + Math.sin(time * 0.6 + p.phase) * 12) * dt;
          p.y += p.vy * dt;
          p.rotation += p.spin * dt;
          if (p.y > height + 20 || p.x > width + 20) Object.assign(p, spawn(false), { x: Math.random() * width - 40 });
          break;
        case "shooting-stars":
          p.phase += dt;
          if (p.phase > 0) {
            p.x += p.vx * dt;
            p.y += p.vy * dt;
          }
          if (p.x > width + p.size || p.y > height + p.size) Object.assign(p, spawn(false));
          break;
        default:
          p.x += p.vx * dt;
          p.y += p.vy * dt;
          if (p.x < -10) p.x = width + 10;
          if (p.x > width + 10) p.x = -10;
          if (p.y < -10) p.y = height + 10;
          if (p.y > height + 10) p.y = -10;
      }
    }

    function draw(p: Particle, time: number) {
      if (!context) return;
      const twinkle = 0.5 + Math.sin(time * 1.4 + p.phase) * 0.5;

      switch (kind) {
        case "petals":
          context.save();
          context.translate(p.x, p.y);
          context.rotate(p.rotation);
          context.globalAlpha = p.alpha;
          context.fillStyle = accentSoft;
          context.beginPath();
          context.ellipse(0, 0, p.size * 0.6, p.size, 0, 0, Math.PI * 2);
          context.fill();
          context.restore();
          break;
        case "shooting-stars": {
          if (p.phase <= 0) return;
          const length = p.size;
          const norm = Math.hypot(p.vx, p.vy);
          const tailX = p.x - (p.vx / norm) * length;
          const tailY = p.y - (p.vy / norm) * length;
          const gradient = context.createLinearGradient(p.x, p.y, tailX, tailY);
          gradient.addColorStop(0, accentSoft);
          gradient.addColorStop(1, "transparent");
          context.globalAlpha = p.alpha;
          context.strokeStyle = gradient;
          context.lineWidth = 1.4;
          context.beginPath();
          context.moveTo(p.x, p.y);
          context.lineTo(tailX, tailY);
          context.stroke();
          break;
        }
        case "sun-glints":
          context.globalAlpha = p.alpha * twinkle;
          context.fillStyle = gold;
          context.fillRect(p.x - p.size, p.y - 0.5, p.size * 2, 1);
          context.fillRect(p.x - 0.5, p.y - p.size, 1, p.size * 2);
          break;
        case "fireflies":
          context.globalAlpha = 0.25 + twinkle * 0.6;
          context.fillStyle = accent;
          context.shadowColor = accent;
          context.shadowBlur = 10;
          context.beginPath();
          context.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          context.fill();
          context.shadowBlur = 0;
          break;
        default:
          context.globalAlpha = p.alpha * (0.4 + twinkle * 0.6);
          context.fillStyle = kind === "projector-dust" ? gold : accentSoft;
          context.beginPath();
          context.arc(p.x, p.y, p.size, 0, Math.PI * 2);
          context.fill();
      }
    }

    function loop(now: number) {
      if (!context) return;
      // dt limitado: voltar de uma aba em segundo plano não pode "teleportar"
      // todas as partículas de uma vez.
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      const time = now / 1000;

      context.clearRect(0, 0, width, height);
      for (const particle of particles) {
        step(particle, dt, time);
        draw(particle, time);
      }
      context.globalAlpha = 1;

      frame = requestAnimationFrame(loop);
    }

    function handleVisibility() {
      cancelAnimationFrame(frame);
      if (document.visibilityState === "visible") {
        last = performance.now();
        frame = requestAnimationFrame(loop);
      }
    }

    resize();
    frame = requestAnimationFrame(loop);
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [kind]);

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-40 h-full w-full" />;
}
