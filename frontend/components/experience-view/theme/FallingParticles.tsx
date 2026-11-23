"use client";

import { useEffect, useRef } from "react";
import type { ParticleKind } from "@/lib/themeRegistry";

const TAU = Math.PI * 2;
const FADE_SECONDS = 0.6;
const STAR_COLORS = ["#FFFFFF", "#DCD0FF", "#B58CFF", "#FFD76A"];
const POPCORN_LOBES = [[-0.46, 0.11], [0.45, 0.03], [0, -0.42], [0.04, 0.36]];
const SHELL_RIB_TIPS = [[-0.42, -0.11], [-0.34, -0.30], [-0.19, -0.39], [0, -0.48], [0.19, -0.39], [0.34, -0.30], [0.42, -0.11]];

type Particle = {
  x: number;
  y: number;
  speed: number;
  size: number;
  alpha: number;
  age: number;
  rotation: number;
  spin: number;
};

type Frame = { width: number; ratio: number; opacity: number };
type ParticleEffect<T extends Particle> = {
  mobileCount: number;
  desktopCount: number;
  spawn: (height: number, initial: boolean) => T;
  renderer: (context: CanvasRenderingContext2D) => (particle: T, frame: Frame) => void;
};

function placeDriftingParticle(context: CanvasRenderingContext2D, particle: Particle & { drift: number }, frame: Frame) {
  const { width, ratio, opacity } = frame;
  const padding = particle.size;
  const span = width + 2 * padding;
  const offset = particle.x * width + particle.age * particle.drift + padding;
  const x = ((offset % span) + span) % span - padding;
  context.setTransform(ratio, 0, 0, ratio, x * ratio, particle.y * ratio);
  context.rotate(particle.rotation);
  context.globalAlpha = opacity * particle.alpha;
}

function makePetal(height: number, initial: boolean) {
  const depth = Math.random();
  const shade = Math.random();

  return {
    x: Math.random(),
    y: initial ? Math.random() * height : -20 - Math.random() * 60,
    speed: 15 + depth * 26,
    size: 8 + depth * 11,
    alpha: 0.3 + depth * 0.5,
    amplitude: 18 + Math.random() * 38,
    frequency: TAU / (6 + Math.random() * 5),
    phase: Math.random() * TAU,
    age: 0,
    rotation: Math.random() * TAU,
    spin: (Math.random() - 0.5) * 0.9,
    flip: 0.5 + Math.random() * 0.7,
    color: shade < 0.65 ? "#FFC2D9" : shade < 0.95 ? "#FF9CC4" : "#FFF0F6",
  };
}

const PETALS: ParticleEffect<ReturnType<typeof makePetal>> = {
  mobileCount: 22,
  desktopCount: 34,
  spawn: makePetal,
  renderer(context) {
    const shape = new Path2D();
    shape.moveTo(0, 0.5);
    shape.bezierCurveTo(0.45, 0.25, 0.4, -0.35, 0.09, -0.5);
    shape.lineTo(0, -0.39);
    shape.lineTo(-0.09, -0.5);
    shape.bezierCurveTo(-0.4, -0.35, -0.45, 0.25, 0, 0.5);
    shape.closePath();

    return (petal, { width, ratio, opacity }) => {
      const x = petal.x * width + Math.sin(petal.age * petal.frequency + petal.phase) * petal.amplitude;
      const scaleX = 0.45 + 0.55 * Math.abs(Math.cos(petal.age * petal.flip + petal.phase));
      context.setTransform(ratio, 0, 0, ratio, x * ratio, petal.y * ratio);
      context.rotate(petal.rotation);
      context.scale(petal.size * scaleX, petal.size);
      context.globalAlpha = opacity * petal.alpha;
      context.fillStyle = petal.color;
      context.fill(shape);
    };
  },
};

function makeStar(height: number, initial: boolean) {
  const depth = Math.random();
  const shade = Math.random();
  const sparkle = Math.random() < 0.3;

  return {
    x: Math.random(),
    y: initial ? Math.random() * height : -12 - Math.random() * 85,
    speed: 12 + depth * 24,
    size: sparkle ? 5 + 7 * depth : 1 + 2.5 * depth,
    alpha: 0.28 + depth * 0.57,
    drift: 3 + Math.random() * 7,
    frequency: TAU / (2 + Math.random() * 3),
    phase: Math.random() * TAU,
    age: 0,
    rotation: (Math.random() - 0.5) * 0.6,
    spin: sparkle ? (Math.random() - 0.5) * 0.5 : 0,
    colorIndex: shade < 0.62 ? 0 : shade < 0.86 ? 1 : shade < 0.97 ? 2 : 3,
    sparkle,
  };
}

function makePointSprite(color: string) {
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = 32;
  const context = sprite.getContext("2d")!;
  const halo = context.createRadialGradient(16, 16, 0, 16, 16, 16);
  halo.addColorStop(0, color);
  halo.addColorStop(0.3, `${color}55`);
  halo.addColorStop(1, `${color}00`);
  context.fillStyle = halo;
  context.fillRect(0, 0, 32, 32);
  context.fillStyle = color;
  context.beginPath();
  context.arc(16, 16, 5, 0, TAU);
  context.fill();
  return sprite;
}

const STARS: ParticleEffect<ReturnType<typeof makeStar>> = {
  mobileCount: 34,
  desktopCount: 52,
  spawn: makeStar,
  renderer(context) {
    const points = STAR_COLORS.map(makePointSprite);
    const sparkle = new Path2D();
    sparkle.moveTo(0, -0.5);
    sparkle.quadraticCurveTo(0.05, -0.05, 0.5, 0);
    sparkle.quadraticCurveTo(0.05, 0.05, 0, 0.5);
    sparkle.quadraticCurveTo(-0.05, 0.05, -0.5, 0);
    sparkle.quadraticCurveTo(-0.05, -0.05, 0, -0.5);
    sparkle.closePath();

    return (star, { width, ratio, opacity }) => {
      const x = (star.x * width + star.age * star.drift + 12) % (width + 24) - 12;
      const twinkle = 0.675 + 0.325 * Math.sin(star.age * star.frequency + star.phase);
      context.setTransform(ratio, 0, 0, ratio, x * ratio, star.y * ratio);
      context.globalAlpha = opacity * star.alpha * twinkle;

      if (star.sparkle) {
        context.rotate(star.rotation);
        context.scale(star.size, star.size);
        context.fillStyle = STAR_COLORS[star.colorIndex];
        context.fill(sparkle);
      } else {
        const diameter = star.size * 3.2;
        context.drawImage(points[star.colorIndex], -diameter / 2, -diameter / 2, diameter, diameter);
      }
    };
  },
};

function makePopcornSprite(color: string) {
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = 64;
  const context = sprite.getContext("2d")!;
  context.translate(32, 32);
  context.scale(26, 26);

  const lobes = POPCORN_LOBES.map(([x, y]) => ({
    x: x + (Math.random() - 0.5) * 0.22,
    y: y + (Math.random() - 0.5) * 0.22,
    radius: 0.5 + Math.random() * 0.1,
  }));

  context.fillStyle = "#C8873A";
  context.beginPath();
  context.ellipse(0.11, 0.82, 0.23, 0.25, Math.PI / 7, 0, TAU);
  context.fill();

  context.fillStyle = color;
  context.beginPath();
  for (const { x, y, radius } of lobes) {
    context.moveTo(x + radius, y);
    context.arc(x, y, radius, 0, TAU);
  }
  context.fill();

  context.fillStyle = "#FFFFFF";
  context.globalAlpha = 0.52;
  context.beginPath();
  for (const { x, y, radius } of lobes) {
    const highlightX = x - radius * 0.26;
    const highlightY = y - radius * 0.33;
    context.moveTo(highlightX + radius * 0.27, highlightY);
    context.arc(highlightX, highlightY, radius * 0.27, 0, TAU);
  }
  context.fill();
  return sprite;
}

function makePopcorn(height: number, initial: boolean) {
  const depth = Math.random();
  const shade = Math.random();

  return {
    x: Math.random(),
    y: initial ? Math.random() * height : -26 - Math.random() * height * 0.25,
    speed: 14 + depth * 24,
    size: 14 + depth * 18,
    alpha: 0.4 + depth * 0.34,
    drift: (Math.random() - 0.5) * 14,
    age: 0,
    rotation: Math.random() * TAU,
    spin: (Math.random() - 0.5) * 1.2,
    sprite: makePopcornSprite(shade < 0.65 ? "#FFF4DA" : shade < 0.93 ? "#FFE9B8" : "#FFD98A"),
  };
}

const POPCORN: ParticleEffect<ReturnType<typeof makePopcorn>> = {
  mobileCount: 18,
  desktopCount: 28,
  spawn: makePopcorn,
  renderer(context) {
    // Compor as bolinhas e os brilhos antes do fade evita acumular
    // opacidade nas sobreposições e permite um draw por pipoca.
    return (popcorn, frame) => {
      placeDriftingParticle(context, popcorn, frame);
      const size = popcorn.size * 1.22;
      context.drawImage(popcorn.sprite, -size / 2, -size / 2, size, size);
    };
  },
};

function makeShellSprite(size: number, color: string) {
  const sprite = document.createElement("canvas");
  sprite.width = sprite.height = 48;
  const context = sprite.getContext("2d")!;
  context.translate(24, 24);
  context.scale(36, 36 * (0.9 + Math.random() * 0.2));

  context.fillStyle = color;
  context.beginPath();
  context.moveTo(0, 0.53);
  context.quadraticCurveTo(-0.27, 0.38, -0.47, 0.07);
  context.quadraticCurveTo(-0.57, -0.07, -0.44, -0.18);
  context.quadraticCurveTo(-0.49, -0.39, -0.28, -0.38);
  context.quadraticCurveTo(-0.23, -0.55, -0.10, -0.46);
  context.quadraticCurveTo(0, -0.59, 0.10, -0.46);
  context.quadraticCurveTo(0.23, -0.55, 0.28, -0.38);
  context.quadraticCurveTo(0.49, -0.39, 0.44, -0.18);
  context.quadraticCurveTo(0.57, -0.07, 0.47, 0.07);
  context.quadraticCurveTo(0.27, 0.38, 0, 0.53);
  context.closePath();
  context.fill();

  context.strokeStyle = "#785028";
  context.globalAlpha = 0.4;
  context.lineWidth = 0.8 / size;
  context.lineCap = "round";
  context.beginPath();
  for (const [x, y] of SHELL_RIB_TIPS) {
    context.moveTo(0, 0.43);
    context.quadraticCurveTo(x * 0.67, 0.09, x, y);
  }
  context.stroke();

  context.fillStyle = "#785028";
  context.globalAlpha = 0.65;
  context.beginPath();
  context.ellipse(0, 0.447, 0.078, 0.052, 0, 0, TAU);
  context.fill();
  return sprite;
}

function makeShell(height: number, initial: boolean) {
  const depth = Math.random();
  const shade = Math.random();
  const size = 9 + depth * 11;
  const color = shade < 0.5 ? "#FFE0BC" : shade < 0.76 ? "#FFC992" : shade < 0.95 ? "#F6EBDD" : "#FFB3A0";

  return {
    x: Math.random(),
    y: initial ? Math.random() * height : -24 - Math.random() * height * 0.25,
    speed: 14 + depth * 22,
    size,
    alpha: 0.35 + depth * 0.42,
    drift: (Math.random() - 0.5) * 16,
    age: 0,
    rotation: Math.random() * TAU,
    spin: (Math.random() - 0.5) * 1.2,
    sprite: makeShellSprite(size, color),
  };
}

const SHELLS: ParticleEffect<ReturnType<typeof makeShell>> = {
  mobileCount: 26,
  desktopCount: 40,
  spawn: makeShell,
  renderer(context) {
    return (shell, frame) => {
      placeDriftingParticle(context, shell, frame);
      const size = shell.size * 48 / 36;
      context.drawImage(shell.sprite, -size / 2, -size / 2, size, size);
    };
  },
};

function makeMoon(height: number, initial: boolean) {
  const depth = Math.random();
  const shade = Math.random();

  return {
    x: Math.random(),
    y: initial ? Math.random() * height : -24 - Math.random() * height * 0.25,
    speed: 12 + depth * 22,
    size: 4 + depth * 5,
    alpha: 0.36 + depth * 0.44,
    drift: (Math.random() - 0.5) * 12,
    age: 0,
    rotation: Math.random() * TAU,
    spin: Math.random() - 0.5,
    color: shade < 0.5 ? "#FFC857" : shade < 0.8 ? "#FFE9A8" : shade < 0.95 ? "#FFF3CC" : "#F0DDA0",
  };
}

const MOONS: ParticleEffect<ReturnType<typeof makeMoon>> = {
  mobileCount: 24,
  desktopCount: 36,
  spawn: makeMoon,
  renderer(context) {
    const offset = 0.45;
    const innerRadius = 0.85;
    // Encaixa os dois arcos no ponto de interseção dos círculos.
    const tipX = (1 + offset ** 2 - innerRadius ** 2) / (2 * offset);
    const outerAngle = Math.acos(tipX);
    const innerAngle = Math.atan2(Math.sin(outerAngle), tipX - offset);
    const crescent = new Path2D();
    crescent.arc(0, 0, 1, -outerAngle, outerAngle, true);
    crescent.arc(offset, 0, innerRadius, innerAngle, -innerAngle);
    crescent.closePath();

    return (moon, frame) => {
      placeDriftingParticle(context, moon, frame);
      context.scale(moon.size, moon.size);
      context.fillStyle = moon.color;
      context.fill(crescent);
    };
  },
};

export default function FallingParticles({ kind, intensity }: {
  kind: ParticleKind;
  intensity: number;
}) {
  switch (kind) {
    case "petals": return <ParticleCanvas key={kind} effect={PETALS} intensity={intensity} />;
    case "shooting-stars": return <ParticleCanvas key={kind} effect={STARS} intensity={intensity} />;
    case "popcorn": return <ParticleCanvas key={kind} effect={POPCORN} intensity={intensity} />;
    case "shells": return <ParticleCanvas key={kind} effect={SHELLS} intensity={intensity} />;
    case "moons": return <ParticleCanvas key={kind} effect={MOONS} intensity={intensity} />;
  }
}

function ParticleCanvas<T extends Particle>({ effect, intensity }: { effect: ParticleEffect<T>; intensity: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const setIntensity = useRef<(value: number) => void>(null);

  useEffect(() => {
    const element = canvasRef.current;
    const canvasContext = element?.getContext("2d");
    if (!element || !canvasContext) return;
    const canvas = element;
    const context = canvasContext;

    const drawParticle = effect.renderer(context);
    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const surface: Frame = { width: 0, ratio: 1, opacity: 0 };
    let height = 0;
    let particles: T[] = [];
    let frame = 0;
    let last = 0;
    let fromOpacity = 0;
    let target = 0;
    let fadeElapsed = 0;

    function clear() {
      context.resetTransform();
      context.clearRect(0, 0, canvas.width, canvas.height);
    }

    function draw(now: number) {
      frame = 0;
      const elapsed = Math.max(0, (now - last) / 1000);
      const dt = Math.min(elapsed, 0.05);
      last = now;
      fadeElapsed = Math.min(fadeElapsed + elapsed, FADE_SECONDS);
      const progress = fadeElapsed / FADE_SECONDS;
      surface.opacity = fromOpacity + (target - fromOpacity) * progress;

      clear();
      if (!surface.opacity && !target) return;

      for (let i = 0; i < particles.length; i++) {
        let particle = particles[i];
        particle.age += dt;
        particle.y += particle.speed * dt;
        particle.rotation += particle.spin * dt;
        if (particle.y > height + 20) {
          particle = particles[i] = effect.spawn(height, false);
        }

        if (particle.y >= -20) drawParticle(particle, surface);
      }

      frame = requestAnimationFrame(draw);
    }

    function start() {
      if (frame || (!target && !surface.opacity) || motionPreference.matches || document.hidden) return;
      last = performance.now();
      frame = requestAnimationFrame(draw);
    }

    function resize() {
      const width = canvas.clientWidth;
      const newHeight = canvas.clientHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      if (width === surface.width && newHeight === height && ratio === surface.ratio) return;

      surface.width = width;
      surface.ratio = ratio;
      height = newHeight;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      const count = width < 640 ? effect.mobileCount : effect.desktopCount;
      particles = Array.from({ length: count }, () => effect.spawn(height, true));
      start();
    }

    function syncMotion() {
      cancelAnimationFrame(frame);
      frame = 0;
      if (motionPreference.matches) {
        clear();
        surface.opacity = 0;
        fromOpacity = 0;
        fadeElapsed = 0;
      }
      start();
    }

    setIntensity.current = (value) => {
      if (value === target) return;
      fromOpacity = surface.opacity;
      target = value;
      fadeElapsed = 0;
      start();
    };

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    motionPreference.addEventListener("change", syncMotion);
    document.addEventListener("visibilitychange", syncMotion);
    return () => {
      setIntensity.current = null;
      cancelAnimationFrame(frame);
      observer.disconnect();
      motionPreference.removeEventListener("change", syncMotion);
      document.removeEventListener("visibilitychange", syncMotion);
    };
  }, [effect]);

  useEffect(() => {
    setIntensity.current?.(intensity);
  }, [intensity]);

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none fixed inset-0 z-40 h-full w-full" />;
}
