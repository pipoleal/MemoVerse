"use client";

import { Stars } from "@react-three/drei";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import UniverseEngine from "@/components/universe/UniverseEngine";
import { LAUNCH_AT_UTC_MS } from "@/lib/launch";

import LaunchMusicPlayer from "./LaunchMusicPlayer";

type Remaining = {
  totalMs: number;
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
};

function computeRemaining(): Remaining {
  const totalMs = Math.max(0, LAUNCH_AT_UTC_MS - Date.now());
  const totalSeconds = Math.floor(totalMs / 1000);
  return {
    totalMs,
    days: Math.floor(totalSeconds / 86400),
    hours: Math.floor((totalSeconds % 86400) / 3600),
    minutes: Math.floor((totalSeconds % 3600) / 60),
    seconds: totalSeconds % 60,
  };
}

// Cada bloco é só texto (número + rótulo) — a informação nunca depende de
// nenhuma animação para ser entendida, só o aparecimento inicial é
// animado (e nem isso, com prefers-reduced-motion). value=null (só antes
// da montagem no cliente, ver comentário em ComingSoonView) mostra "--"
// em vez de um número.
function CountdownUnit({ value, label }: { value: number | null; label: string }) {
  return (
    <div className="flex w-16 flex-col items-center gap-1 sm:w-20">
      <span className="text-4xl font-black tabular-nums text-white sm:text-5xl md:text-6xl">
        {value === null ? "--" : value.toString().padStart(2, "0")}
      </span>
      <span className="text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-400 sm:text-xs">
        {label}
      </span>
    </div>
  );
}

// Delay de entrada por elemento via CSS puro (.fade-up + animation-delay
// inline, ver globals.css) — não framer-motion. Motivo: confirmado ao vivo
// em produção (next build && next start, sem Canvas, sem LaunchMusicPlayer,
// sem re-renders do countdown, com useReducedMotion() travado em false —
// eliminando uma a uma toda outra variável) que a transição initial→animate
// do framer-motion 13 simplesmente nunca dispara neste build de produção
// (Next.js 16 + React 19.2) — os elementos ficam presos para sempre no
// estado "initial" (opacity:0), tornando a página inteira invisível para
// quem visita, apesar do conteúdo existir no DOM. Nunca reproduziu em
// `next dev` (que não passa pela otimização/pipeline de build real) — só
// apareceu com o build de produção de verdade. CSS puro não depende de
// nenhum ciclo de vida de biblioteca JS para disparar a animação — o
// navegador já cuida disso sozinho a partir do primeiro paint do elemento,
// funciona de forma idêntica em SSR/hidratação/produção, e ainda respeita
// prefers-reduced-motion nativamente (ver globals.css), sem precisar do
// hook useReducedMotion() do framer-motion (que tem seu próprio problema
// documentado de divergir entre servidor `null` e cliente `boolean` no
// primeiro render).
function fadeUpStyle(delaySeconds: number): React.CSSProperties {
  return { animationDelay: `${delaySeconds}s` };
}

export default function ComingSoonView() {
  const router = useRouter();

  // null até o primeiro efeito rodar no cliente (nunca calculado durante
  // SSR nem durante o próprio render de hidratação) — Date.now() muda
  // entre o render do servidor e o da hidratação por causa do tempo real
  // de rede/parse decorrido, então calcular o valor real num useState()
  // com inicializador de função (que roda nos DOIS renders) causava
  // mismatch de hidratação (visto ao vivo: 29 vs 30 segundos). null é
  // idêntico nos dois lados; o valor de verdade só existe depois que o
  // efeito abaixo roda, sempre pós-hidratação.
  const [remaining, setRemaining] = useState<Remaining | null>(null);
  // Ref, não state: só precisa sobreviver entre execuções do efeito
  // abaixo para nunca pedir um segundo refresh — não deve, por si só,
  // acionar um re-render.
  const hasRequestedRefresh = useRef(false);

  useEffect(() => {
    // Mesmo padrão já usado em GalaxyHub.tsx/ForgotPasswordFlow.tsx: esta
    // primeira leitura só pode acontecer no cliente, pós-hidratação (é
    // exatamente o valor que não pode existir durante SSR, ver comentário
    // acima em useState) — não é o caso que a regra normalmente pega
    // (sincronizar com um valor que já dava pra derivar durante o render).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRemaining(computeRemaining());

    const interval = window.setInterval(() => {
      setRemaining(computeRemaining());
    }, 1000);

    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (remaining === null || remaining.totalMs > 0 || hasRequestedRefresh.current) return;

    // O relógio do visitante pode estar errado — isto só pede uma
    // NAVEGAÇÃO nova para "/". A decisão real (mostrar esta página de
    // novo ou a Home de verdade) é sempre revalidada por middleware.ts no
    // servidor a cada requisição, nunca por este componente.
    hasRequestedRefresh.current = true;
    router.refresh();
  }, [remaining, router]);

  return (
    <main className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden px-6 py-16 text-center">
      <div className="absolute inset-0 -z-10">
        {/* UniverseEngine direto (não o wrapper Universe, que não aceita
            filhos) — shootingStars já existe e é opt-in (mesmo componente
            de GalaxyChapter.tsx, intocado); a camada extra de Stars aqui é
            só mais uma instância do MESMO componente do drei que Scene.tsx
            já usa, com contagem/velocidade diferentes para dar mais
            densidade e brilho — nenhum arquivo compartilhado por outras
            páginas foi alterado. */}
        <UniverseEngine shootingStars>
          <Stars radius={140} depth={60} count={7000} factor={4.5} saturation={0} fade speed={1.4} />
        </UniverseEngine>
      </div>

      <LaunchMusicPlayer />

      <div className="relative z-10 flex max-w-2xl flex-col items-center">
        <p
          style={fadeUpStyle(0.1)}
          className="fade-up mb-6 text-xs font-semibold uppercase tracking-[0.4em] text-yellow-400 sm:text-sm"
        >
          Lançamento em breve
        </p>

        <h1
          style={fadeUpStyle(0.3)}
          className="fade-up bg-linear-to-r from-white via-slate-200 to-yellow-300 bg-clip-text text-6xl font-black tracking-tight text-transparent sm:text-7xl md:text-8xl"
        >
          MemoVerse
        </h1>

        <p style={fadeUpStyle(0.5)} className="fade-up mt-6 text-lg text-slate-300 sm:text-xl">
          Suas memórias merecem um universo.
        </p>

        <div
          style={fadeUpStyle(0.7)}
          role="timer"
          aria-label={
            remaining === null
              ? "Calculando tempo restante para o lançamento"
              : remaining.totalMs > 0
                ? `Faltam ${remaining.days} dias, ${remaining.hours} horas, ${remaining.minutes} minutos e ${remaining.seconds} segundos para o lançamento`
                : "É hora de começar"
          }
          className="fade-up mt-10 flex flex-col items-center gap-4"
        >
          {remaining === null || remaining.totalMs > 0 ? (
            <div className="flex items-start gap-3 sm:gap-6">
              <CountdownUnit value={remaining?.days ?? null} label="Dias" />
              <span className="pt-1 text-3xl font-light text-slate-600 sm:text-4xl">:</span>
              <CountdownUnit value={remaining?.hours ?? null} label="Horas" />
              <span className="pt-1 text-3xl font-light text-slate-600 sm:text-4xl">:</span>
              <CountdownUnit value={remaining?.minutes ?? null} label="Minutos" />
              <span className="pt-1 text-3xl font-light text-slate-600 sm:text-4xl">:</span>
              <CountdownUnit value={remaining?.seconds ?? null} label="Segundos" />
            </div>
          ) : (
            <p className="text-2xl font-bold text-yellow-300 sm:text-3xl">É hora de começar.</p>
          )}

          <p className="text-sm text-slate-400 sm:text-base">31 de agosto · 18:00</p>
        </div>

        <p style={fadeUpStyle(0.9)} className="fade-up mt-10 max-w-md text-sm text-slate-400 sm:text-base">
          Prepare-se para transformar momentos especiais em experiências inesquecíveis.
        </p>
      </div>
    </main>
  );
}
