"use client";

import { useEffect, useRef } from "react";

type StarFieldPhase =
  | "idle"
  | "transition"
  | "burst"
  | "converge";

type StarFieldProps = {
  phase?: StarFieldPhase;
};

type StarData = {
  left: number;
  top: number;
  size: number;
  angle: number;
  distance: number;
  orbitDistance: number;
  delay: number;
  burstDistance: number;
  duration: number;
};

const STAR_COUNT = 500;

function pseudoRandom(value: number) {
  const result =
    Math.sin(value * 12.9898) *
    43758.5453;

  return Math.abs(result % 1);
}

function createStars(): StarData[] {
  return Array.from(
    { length: STAR_COUNT },
    (_, index) => {
      const randomA =
        pseudoRandom(index + 1);

      const randomB =
        pseudoRandom(index + 1000);

      const randomC =
        pseudoRandom(index + 2000);

      const randomD =
        pseudoRandom(index + 3000);

      const randomE =
        pseudoRandom(index + 4000);

      const left =
        randomA * 100;

      const top =
        randomB * 100;

      const centerX =
        left - 50;

      const centerY =
        top - 50;

      const distance = Math.sqrt(
        centerX * centerX +
          centerY * centerY
      );

      const angle = Math.atan2(
        centerY,
        centerX
      );

      const size =
        randomC > 0.94
          ? 2
          : randomC > 0.7
            ? 1.5
            : 1;

      const orbitDistance =
        Math.min(
          35 + randomD * 65,
          100
        );

      const delay =
        randomE * 500;

      const burstDistance =
        250 + randomD * 550;

      const duration =
        1400 + randomE * 900;

      return {
        left,
        top,
        size,
        angle,
        distance,
        orbitDistance,
        delay,
        burstDistance,
        duration,
      };
    }
  );
}

export default function StarField({
  phase = "idle",
}: StarFieldProps) {
  const stars = useRef<StarData[] | null>(
    null
  );

  const containerRef =
    useRef<HTMLDivElement | null>(null);

  const starRefs =
    useRef<(HTMLSpanElement | null)[]>(
      []
    );

  /*
   * Criamos as estrelas apenas uma vez.
   *
   * Isso evita que as posições mudem
   * quando o React renderizar novamente.
   */
  if (!stars.current) {
    stars.current = createStars();
  }

  /*
   * ========================================
   * ANIMAÇÃO
   * ========================================
   */

  useEffect(() => {
    const elements =
      starRefs.current;

    if (!elements.length) {
      return;
    }

    /*
     * Cancela qualquer animação anterior.
     */
    elements.forEach((element) => {
      if (!element) {
        return;
      }

      element.getAnimations().forEach(
        (animation) => {
          animation.cancel();
        }
      );
    });

    /*
     * ========================================
     * IDLE
     * ========================================
     */

    if (phase === "idle") {
      elements.forEach(
        (element, index) => {
          if (!element) {
            return;
          }

          const star =
            stars.current?.[index];

          if (!star) {
            return;
          }

          element.style.opacity =
            "0.45";

          element.style.transform =
            "translate3d(0, 0, 0)";

          /*
           * Pequena pulsação individual.
           */
          element.animate(
            [
              {
                opacity: 0.25,
                transform:
                  "scale(0.8)",
              },
              {
                opacity: 0.75,
                transform:
                  "scale(1.35)",
              },
              {
                opacity: 0.25,
                transform:
                  "scale(0.8)",
              },
            ],
            {
              duration:
                1800 +
                star.delay * 2,
              delay:
                star.delay,
              iterations:
                Infinity,
              easing:
                "ease-in-out",
            }
          );
        }
      );

      return;
    }

    /*
     * ========================================
     * TRANSITION
     * ========================================
     *
     * As estrelas começam a se mover
     * ao redor do centro.
     */

    if (phase === "transition") {
      elements.forEach(
        (element, index) => {
          if (!element) {
            return;
          }

          const star =
            stars.current?.[index];

          if (!star) {
            return;
          }

          const tangentX =
            -Math.sin(
              star.angle
            ) *
            star.orbitDistance;

          const tangentY =
            Math.cos(
              star.angle
            ) *
            star.orbitDistance;

          element.style.opacity =
            "0.8";

          element.animate(
            [
              {
                transform:
                  "translate3d(0, 0, 0) scale(1)",
              },
              {
                transform:
                  `translate3d(
                    ${tangentX}px,
                    ${tangentY}px,
                    0
                  )
                  scale(1.15)`,
              },
              {
                transform:
                  `translate3d(
                    ${tangentX * -0.45}px,
                    ${tangentY * -0.45}px,
                    0
                  )
                  scale(1.05)`,
              },
              {
                transform:
                  "translate3d(0, 0, 0) scale(1)",
              },
            ],
            {
              duration:
                2600 +
                star.delay,
              delay:
                star.delay,
              iterations:
                Infinity,
              easing:
                "ease-in-out",
            }
          );
        }
      );

      return;
    }

    /*
     * ========================================
     * BURST
     * ========================================
     *
     * Agora as estrelas aceleram.
     */

    if (phase === "burst") {
      elements.forEach(
        (element, index) => {
          if (!element) {
            return;
          }

          const star =
            stars.current?.[index];

          if (!star) {
            return;
          }

          /*
           * Direção radial.
           */
          const targetX =
            Math.cos(
              star.angle
            ) *
            star.burstDistance;

          const targetY =
            Math.sin(
              star.angle
            ) *
            star.burstDistance;

          element.style.opacity =
            "1";

          element.animate(
            [
              {
                transform:
                  "translate3d(0, 0, 0) scale(1)",
                opacity: 0.7,
              },
              {
                transform:
                  "translate3d(0, 0, 0) scale(2)",
                opacity: 1,
              },
              {
                transform:
                  `translate3d(
                    ${targetX}px,
                    ${targetY}px,
                    0
                  )
                  scale(3.2)`,
                opacity: 0,
              },
            ],
            {
              duration:
                star.duration,
              delay:
                star.delay,
              fill: "forwards",
              easing:
                "cubic-bezier(0.12, 0.8, 0.2, 1)",
            }
          );
        }
      );

      return;
    }

    /*
     * ========================================
     * CONVERGE
     * ========================================
     *
     * Aqui fazemos o efeito cinematográfico:
     *
     * estrelas espalhadas
     *       ↓
     * começam a voltar
     *       ↓
     * tudo converge
     *       ↓
     * ponto central
     */

    if (phase === "converge") {
      elements.forEach(
        (element, index) => {
          if (!element) {
            return;
          }

          const star =
            stars.current?.[index];

          if (!star) {
            return;
          }

          /*
           * A posição atual foi criada usando
           * left/top em porcentagem.
           *
           * Para chegar ao centro:
           *
           * X = 50% - posição atual
           * Y = 50% - posição atual
           */
          const targetX =
            (50 - star.left) *
            (window.innerWidth / 100);

          const targetY =
            (50 - star.top) *
            (window.innerHeight / 100);

          element.style.opacity =
            "0";

          element.animate(
            [
              {
                transform:
                  `translate3d(
                    ${Math.cos(star.angle) * star.burstDistance}px,
                    ${Math.sin(star.angle) * star.burstDistance}px,
                    0
                  )
                  scale(2.8)`,

                opacity: 0,
              },
              {
                transform:
                  `translate3d(
                    ${targetX * 0.35}px,
                    ${targetY * 0.35}px,
                    0
                  )
                  scale(1.5)`,

                opacity: 0.8,
              },
              {
                transform:
                  `translate3d(
                    ${targetX}px,
                    ${targetY}px,
                    0
                  )
                  scale(0.15)`,

                opacity: 0,
              },
            ],
            {
              duration:
                2200 +
                star.delay,
              delay:
                star.delay * 0.15,
              fill: "forwards",
              easing:
                "cubic-bezier(0.65, 0, 0.25, 1)",
            }
          );
        }
      );
    }
  }, [phase]);

  return (
    <div
      ref={containerRef}
      className="
        pointer-events-none
        absolute
        inset-0
        overflow-hidden
      "
    >
      {stars.current.map(
        (star, index) => (
          <span
            key={index}
            ref={(element) => {
              starRefs.current[index] =
                element;
            }}
            className="
              absolute
              rounded-full
              bg-white
              will-change-transform
            "
            style={{
              left: `${star.left}%`,
              top: `${star.top}%`,
              width: `${star.size}px`,
              height: `${star.size}px`,
              opacity: 0.45,
              boxShadow:
                star.size >= 2
                  ? "0 0 8px 2px rgba(255,255,255,0.35)"
                  : "none",
            }}
          />
        )
      )}
    </div>
  );
}