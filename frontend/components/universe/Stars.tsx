"use client";

import { Stars as DreiStars } from "@react-three/drei";

export default function Stars() {
  return (
    <DreiStars
      radius={250}
      depth={80}
      count={12000}
      factor={6}
      saturation={0}
      fade
      speed={0.35}
    />
  );
}