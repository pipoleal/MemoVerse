"use client";

import { useEffect, useId, useRef } from "react";

const TAU = Math.PI * 2;
const CENTER_X = 200;
const CENTER_Y = 170;
const TRAIL = Array.from({ length: 18 }, (_, index) => -0.06 * (index + 1));
const COLORS = ["#DCDDFF", "#FFFFFF"];

type MemoryOrbitProps = { year?: string; recipient: string; active: boolean; color: string };

export default function MemoryOrbit({ year, recipient, active, color }: MemoryOrbitProps) {
  const orbitRef = useRef<SVGSVGElement>(null);
  const haloId = useId();

  useEffect(() => {
    const svg = orbitRef.current!;
    const ring = svg.querySelector("circle[data-ring]")!;
    const yearText = svg.querySelector<SVGTextElement>("[data-year]");
    const labels = Array.from(svg.querySelectorAll<SVGTextElement>("[data-label]"));
    const stars = svg.querySelectorAll<SVGGElement>("[data-star]");
    const dots = svg.querySelectorAll("[data-trail]");
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let labelWidths: number[] = [];
    let radius = 122;
    let frame = 0;
    let start: number | undefined;
    let cancelled = false;

    function place(time: number) {
      const first = -Math.PI / 2 + time * TAU / 16;
      const gap = (115 + 35 * Math.sin(TAU * time / 9)) * Math.PI / 180;

      [first, first - gap].forEach((angle, index) => {
        const x = Math.cos(angle);
        const y = Math.sin(angle);
        const labelRadius = radius + 16 + labelWidths[index] / 2 * Math.abs(x) + 9 * Math.abs(y);
        stars[index].setAttribute("transform", `rotate(${angle * 180 / Math.PI})`);
        labels[index].setAttribute("x", String(x * labelRadius));
        labels[index].setAttribute("y", String(y * labelRadius));
      });
    }

    function tick(now: number) {
      start ??= now;
      place((now - start) / 1000);
      frame = requestAnimationFrame(tick);
    }

    function syncMotion() {
      cancelAnimationFrame(frame);
      start = undefined;
      if (active && !preference.matches && !document.hidden) {
        frame = requestAnimationFrame(tick);
      } else if (preference.matches) {
        place(0);
      }
    }

    function layout() {
      if (cancelled) return;
      labelWidths = labels.map((label) => {
        label.removeAttribute("textLength");
        const width = label.getComputedTextLength();
        if (width > 118) label.setAttribute("textLength", "118");
        return Math.min(width, 118);
      });
      radius = Math.min(122, CENTER_X - 24 - Math.max(...labelWidths));
      ring.setAttribute("r", String(radius));
      stars.forEach((star) => star.querySelector("[data-head]")!.setAttribute("transform", `translate(${radius} 0)`));
      dots.forEach((dot, index) => {
        const offset = TRAIL[index % TRAIL.length];
        dot.setAttribute("cx", String(radius * Math.cos(offset)));
        dot.setAttribute("cy", String(radius * Math.sin(offset)));
      });

      if (yearText) {
        yearText.removeAttribute("textLength");
        yearText.setAttribute("x", "0");
        yearText.setAttribute("y", "0");
        yearText.setAttribute("font-size", String(radius * 0.8));
        if (yearText.getComputedTextLength() > radius * 1.3) {
          yearText.setAttribute("textLength", String(radius * 1.3));
        }
        const box = yearText.getBBox();
        yearText.setAttribute("x", String(-box.x - box.width / 2));
        yearText.setAttribute("y", String(-box.y - box.height / 2));
      }

      place(start === undefined ? 0 : (performance.now() - start) / 1000);
    }

    layout();
    void document.fonts.ready.then(layout);
    syncMotion();
    preference.addEventListener("change", syncMotion);
    document.addEventListener("visibilitychange", syncMotion);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      preference.removeEventListener("change", syncMotion);
      document.removeEventListener("visibilitychange", syncMotion);
    };
  }, [active, recipient, year]);

  return (
    <svg
      ref={orbitRef}
      viewBox="0 0 400 340"
      role="img"
      aria-label={`${recipient} e você em órbita${year ? ` · ${year}` : ""}`}
      className="mv-serif mv-rise relative w-full max-w-[25rem] shrink-0"
    >
      <defs>
        <radialGradient id={haloId}>
          <stop offset="0%" stopColor="#DCDDFF" stopOpacity=".37" />
          <stop offset="100%" stopColor="#DCDDFF" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g transform={`translate(${CENTER_X} ${CENTER_Y})`}>
        <circle data-ring="" r="122" fill="none" stroke={color} strokeOpacity=".28" vectorEffect="non-scaling-stroke" />
        {year && (
          <text data-year="" y="31" textAnchor="middle" fontSize="98" fill={color} fillOpacity=".16" lengthAdjust="spacingAndGlyphs" className="[font-variant-numeric:lining-nums]">
            {year}
          </text>
        )}
        {COLORS.map((starColor) => (
          <g key={starColor} data-star="" fill={starColor}>
            {TRAIL.map((offset, i) => {
              const fade = 1 - i / (TRAIL.length - 1);
              return <circle key={offset} data-trail="" r={0.5 + 2 * fade} opacity={0.7 * fade} />;
            })}
            <g data-head="">
              <circle r="22" fill={`url(#${haloId})`} />
              <circle r="8" />
            </g>
          </g>
        ))}
        {[recipient, "você"].map((label, index) => (
          <text key={index} data-label="" textAnchor="middle" dominantBaseline="central" fontSize="20" fontStyle="italic" fill={color} lengthAdjust="spacingAndGlyphs">
            {label}
          </text>
        ))}
      </g>
    </svg>
  );
}
