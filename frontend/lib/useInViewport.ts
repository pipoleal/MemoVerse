"use client";

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";

type UseInViewportOptions = {
  rootMargin?: string;
  threshold?: number;
  once?: boolean;
};

/**
 * Observa se um elemento está (ou já esteve, com `once`) visível na viewport,
 * via IntersectionObserver. Aceita um ref externo para permitir que o mesmo
 * elemento seja observado por mais de uma instância (ex: um gate de lazy-mount
 * e um gate de play/pause simultâneos).
 */
export function useInViewport<T extends Element>(
  { rootMargin = "0px", threshold = 0, once = false }: UseInViewportOptions = {},
  externalRef?: RefObject<T | null>
) {
  const internalRef = useRef<T | null>(null);
  const ref = externalRef ?? internalRef;
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsInView(entry.isIntersecting);

        if (entry.isIntersecting && once) {
          observer.disconnect();
        }
      },
      { rootMargin, threshold }
    );

    observer.observe(element);

    return () => observer.disconnect();
  }, [rootMargin, threshold, once, ref]);

  return { ref, isInView };
}
