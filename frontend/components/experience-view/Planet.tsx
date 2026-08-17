"use client";

export default function Planet() {
  return (
    <div className="relative flex h-64 w-64 items-center justify-center md:h-80 md:w-80">
      <div className="absolute inset-0 rounded-full bg-blue-500/10 blur-3xl" />

      <div
        className="
          relative
          h-48
          w-48
          rounded-full
          bg-[radial-gradient(circle_at_30%_30%,#ffffff_0%,#8ed6ff_8%,#2563eb_35%,#0f172a_75%)]
          shadow-[0_0_80px_rgba(59,130,246,0.45)]
          md:h-64
          md:w-64
        "
      >
        <div className="absolute inset-0 overflow-hidden rounded-full">
          <div
            className="
              absolute
              -left-10
              top-10
              h-20
              w-32
              rounded-[50%]
              bg-emerald-400/30
              blur-md
            "
          />

          <div
            className="
              absolute
              right-0
              top-24
              h-16
              w-28
              rounded-[50%]
              bg-emerald-500/20
              blur-md
            "
          />

          <div
            className="
              absolute
              bottom-8
              left-14
              h-12
              w-24
              rounded-[50%]
              bg-emerald-400/20
              blur-md
            "
          />
        </div>

        <div className="absolute inset-0 rounded-full bg-linear-to-r from-transparent via-white/5 to-black/40" />
      </div>
    </div>
  );
}