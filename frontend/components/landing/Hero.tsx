import Image from "next/image";

// CSS puro (.fade-up, ver globals.css) em vez de framer-motion initial/animate
// — mesmo motivo documentado em ComingSoonView.tsx: a transição
// initial->animate do framer-motion 13 nunca dispara no build de produção
// real (Next.js 16 + React 19.2), deixando o elemento preso em opacity:0
// para sempre. Este componente nunca tinha sido exercitado em produção de
// verdade até agora (middleware.ts sempre serviu /coming-soon no lugar de
// "/"), então o mesmo bug — invisível em `next dev` — só apareceria no
// instante do lançamento. CSS puro não depende de nenhum ciclo de vida de
// biblioteca JS, funciona igual em SSR/hidratação/produção, e já respeita
// prefers-reduced-motion nativamente.
function fadeUpStyle(delaySeconds: number): React.CSSProperties {
  return { animationDelay: `${delaySeconds}s` };
}

export default function Hero() {
  return (
    <section className="relative z-10 flex flex-col items-center px-6 text-center">
      <p
        style={fadeUpStyle(0.1)}
        className="fade-up mb-2 text-xs font-semibold uppercase tracking-[0.4em] text-yellow-400 sm:text-sm"
      >
        Bem-vindo ao
      </p>

      {/* Logo real (lua crescente + estrelas + "MEMOVERSE" + assinatura
          "every memory becomes a star") — recorte de public/brand, ver
          lib/fonts.ts para o porquê de não recriar essa tipografia em CSS. */}
      <div style={fadeUpStyle(0.3)} className="fade-up relative h-56 w-56 sm:h-72 sm:w-72">
        <Image src="/brand/memoverse-lockup.png" alt="MemoVerse — every memory becomes a star" fill priority className="object-contain" />
      </div>

      <p
        style={fadeUpStyle(0.6)}
        className="fade-up mt-2 text-lg font-bold uppercase tracking-[0.2em] text-white sm:text-2xl"
      >
        Suas memórias merecem um universo
      </p>

      <div style={fadeUpStyle(1)} className="fade-up mt-10 text-yellow-400/70">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6 animate-bounce">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </div>
    </section>
  );
}
