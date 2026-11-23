"use client";

import { useEffect, useRef, type CSSProperties, type PointerEvent, type ReactNode } from "react";

type Drag = {
  pointerId: number;
  x: number;
  y: number;
  lastX: number;
  lastTime: number;
  velocity: number;
  startOffset: number;
  horizontal: boolean;
};

type MemoryCarouselProps = {
  index: number;
  count: number;
  active: boolean;
  onNavigate: (slide: number) => void;
  children: ReactNode;
};

export default function MemoryCarousel({ index, count, active, onNavigate, children }: MemoryCarouselProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const drag = useRef<Drag | null>(null);
  const suppressClick = useRef(false);

  useEffect(() => {
    if (!active) return;

    function handleKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const target = event.target;
      if (target instanceof Element && target.closest("input, textarea, select, [contenteditable], video[controls]")) return;
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      const direction = event.key === "ArrowRight" ? 1 : -1;
      onNavigate(Math.max(0, Math.min(count - 1, index + direction)) + 1);
    }

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [active, count, index, onNavigate]);

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (!event.isPrimary || event.button !== 0) return;
    suppressClick.current = false;
    drag.current = {
      pointerId: event.pointerId,
      x: event.clientX,
      y: event.clientY,
      lastX: event.clientX,
      lastTime: event.timeStamp,
      velocity: 0,
      startOffset: 0,
      horizontal: false,
    };
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    const track = trackRef.current!;
    if (!current || current.pointerId !== event.pointerId) return;

    const dx = event.clientX - current.x;
    const elapsed = event.timeStamp - current.lastTime;
    if (elapsed > 0 && event.clientX !== current.lastX) {
      current.velocity = (event.clientX - current.lastX) / elapsed;
      current.lastTime = event.timeStamp;
      current.lastX = event.clientX;
    }

    if (!current.horizontal) {
      const dy = event.clientY - current.y;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 8) return;
      if (Math.abs(dx) <= Math.abs(dy)) {
        drag.current = null;
        return;
      }
      current.horizontal = true;
      event.currentTarget.setPointerCapture(event.pointerId);
      const transform = getComputedStyle(track).transform;
      const offset = transform === "none" ? 0 : new DOMMatrixReadOnly(transform).m41;
      current.startOffset = offset + index * event.currentTarget.clientWidth;
      track.style.transitionDuration = "0ms";
    }

    const atEdge = (index === 0 && dx > 0) || (index === count - 1 && dx < 0);
    track.style.setProperty("--mv-drag-x", `${current.startOffset + dx * (atEdge ? 0.3 : 1)}px`);
  }

  function finishDrag(event: PointerEvent<HTMLDivElement>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    drag.current = null;
    if (!current.horizontal) return;

    suppressClick.current = true;
    const track = trackRef.current!;
    track.style.removeProperty("transition-duration");
    track.style.removeProperty("--mv-drag-x");
    if (event.type !== "pointerup") return;

    const dx = event.clientX - current.x;
    const flick = event.timeStamp - current.lastTime < 80 && dx * current.velocity > 0 && Math.abs(current.velocity) > 0.4;
    if (Math.abs(dx) > event.currentTarget.clientWidth * 0.18 || flick) {
      const next = index + (dx < 0 ? 1 : -1);
      onNavigate(Math.max(0, Math.min(count - 1, next)) + 1);
    }
  }

  return (
    <div
      role="region"
      aria-label="Memórias"
      className="h-full touch-pan-y overflow-clip"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={finishDrag}
      onPointerCancel={finishDrag}
      onLostPointerCapture={finishDrag}
      onDragStart={(event) => event.preventDefault()}
      onClickCapture={(event) => {
        if (!suppressClick.current || event.detail === 0) return;
        suppressClick.current = false;
        event.preventDefault();
        event.stopPropagation();
      }}
    >
      <div
        ref={trackRef}
        className="mv-memory-track flex h-full select-none"
        style={{ "--mv-memory-slide": `${-index * 100}%` } as CSSProperties}
      >
        {children}
      </div>
    </div>
  );
}
