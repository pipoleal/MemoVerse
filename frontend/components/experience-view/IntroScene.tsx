"use client";

import { useEffect, useState } from "react";

import Planet from "./Planet";

type Props = {
  recipient?: string;
  onComplete?: () => void;
};

export default function IntroScene({
  recipient,
  onComplete,
}: Props) {
  const [showMessage, setShowMessage] = useState(false);
  const [showSecondMessage, setShowSecondMessage] =
    useState(false);

  useEffect(() => {
    const messageTimer = setTimeout(() => {
      setShowMessage(true);
    }, 1800);

    const secondTimer = setTimeout(() => {
      setShowSecondMessage(true);
    }, 4200);

    return () => {
      clearTimeout(messageTimer);
      clearTimeout(secondTimer);
    };
  }, []);

  return (
    <section className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-black text-white">
      {/* ESTRELAS */}
      <div className="absolute inset-0">
        <div className="absolute left-[12%] top-[20%] h-1 w-1 rounded-full bg-white opacity-70" />
        <div className="absolute left-[25%] top-[65%] h-1.5 w-1.5 rounded-full bg-white opacity-50" />
        <div className="absolute left-[70%] top-[18%] h-1 w-1 rounded-full bg-white opacity-70" />
        <div className="absolute left-[82%] top-[68%] h-1.5 w-1.5 rounded-full bg-white opacity-60" />
        <div className="absolute left-[55%] top-[78%] h-1 w-1 rounded-full bg-white opacity-50" />
        <div className="absolute left-[42%] top-[12%] h-1 w-1 rounded-full bg-white opacity-60" />
      </div>

      {/* PLANETA */}
      <div
        className={`
          absolute
          transition-all
          duration-2500ms
          ease-out
          ${
            showMessage
              ? "scale-75 opacity-40 blur-[1px]"
              : "scale-100 opacity-100"
          }
        `}
      >
        <Planet />
      </div>

      {/* TEXTO */}
      <div
        className={`
          relative
          z-10
          max-w-4xl
          px-6
          text-center
          transition-all
          duration-1500
          ${
            showMessage
              ? "translate-y-0 opacity-100"
              : "translate-y-8 opacity-0"
          }
        `}
      >
        <p className="text-sm font-medium uppercase tracking-[0.4em] text-yellow-400">
          Uma história entre bilhões
        </p>

        <h1 className="mt-8 text-4xl font-black leading-tight md:text-6xl lg:text-7xl">
          Entre 8 bilhões de pessoas no mundo...
        </h1>

        <p
          className={`
            mt-8
            text-2xl
            font-light
            text-slate-300
            transition-all
            duration-1500
            md:text-4xl
            ${
              showSecondMessage
                ? "translate-y-0 opacity-100"
                : "translate-y-5 opacity-0"
            }
          `}
        >
          eu escolhi{" "}
          <span className="font-semibold text-white">
            {recipient || "você"}
          </span>
          . ❤️
        </p>

        {showSecondMessage && (
          <button
            type="button"
            onClick={onComplete}
            className="
              mt-14
              rounded-full
              border
              border-white/20
              bg-white/5
              px-8
              py-4
              text-sm
              font-semibold
              text-white
              backdrop-blur-xl
              transition-all
              duration-300
              hover:scale-105
              hover:border-yellow-400
              hover:bg-yellow-400/10
            "
          >
            Continuar
          </button>
        )}
      </div>
    </section>
  );
}