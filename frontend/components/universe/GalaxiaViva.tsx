"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Cormorant_Garamond, Fraunces } from "next/font/google";
import YouTube from "react-youtube";

import { extractYouTubeVideoId, isValidYouTubeUrl } from "@/lib/youtube";

// Porta de components/universe (ver frontend/CLAUDE.md: sistemas novos de
// Galáxia vivem aqui, nunca uma segunda implementação em outro lugar) do
// protótipo autocontido galaxia-viva-componente.html — mesmo comportamento
// visual (contador ao vivo, uma estrela por dia vivido, nascimento em
// tempo real, estrela cadente ocasional), só adaptado para se encaixar
// neste projeto:
//
// - `data-since`/`GalaxiaViva.init()` (init global, auto-disparado em
//   DOMContentLoaded) viraram uma prop React (`since: Date`) — este
//   componente monta/desmonta via navegação SPA, nunca só uma vez no
//   carregamento da página.
// - `.card { position: fixed; inset: 22px }` e as regras em `html, body`
//   do arquivo original assumiam ser a página inteira sozinha — removidas;
//   este componente preenche o container que o chamador der a ele
//   (width/height 100% do pai), nunca o viewport inteiro.
// - Fontes (Fraunces, Cormorant Garamond) entram via next/font/google, não
//   <link> para fonts.googleapis.com — o CSP do projeto (middleware.ts) só
//   libera font-src 'self'; next/font resolve isso baixando as fontes no
//   build e servindo de /_next/static/media, mesmo padrão já usado por
//   Geist/Geist Mono em app/layout.tsx.
// - O texto acessível (.sr-only) e o suporte a prefers-reduced-motion do
//   original foram mantidos.
// - Todo seletor CSS foi escopado sob .galaxia-viva (nunca html/body/:root
//   globais) para não vazar nem colidir com o resto do app.
// - Corrigido um typo real do arquivo original (`padding: 0;j` — o `j`
//   sobrando quebrava só essa declaração).
//
// O loop de desenho do céu (60fps, canvas 2D + requestAnimationFrame) fica
// inteiramente fora do ciclo de render do React — muta um array via ref,
// nunca state (mesmo motivo de MemoryStars.tsx mutar BufferAttributes
// direto: setState a cada frame para uma animação contínua thrasharia o
// React à toa). Já o contador/relógio, que só muda uma vez por segundo,
// usa state normal — não precisa da mesma cautela.

const fraunces = Fraunces({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  style: ["normal"],
  variable: "--gv-font-fraunces",
  display: "swap",
});

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  variable: "--gv-font-cormorant",
  display: "swap",
});

type GalaxiaVivaProps = {
  // Instante a partir do qual dias/estrelas são contados. Quem chama
  // decide de onde vem (ex.: meia-noite local do event_date de uma
  // experiência) — este componente não tem opinião sobre isso.
  since: Date;
  className?: string;
  // Etapa Galáxia Viva (música): link de YouTube colado pelo dono na Etapa
  // 7 do wizard (ExperienceDraft.galaxy_live_music_url) — quem chama
  // decide de onde vem, mesma filosofia de `since`. Ausente/vazio/inválido
  // (extractYouTubeVideoId retorna null) nunca é um erro: só não renderiza
  // o botão de música. NUNCA autoplay — só toca a partir de um clique real
  // no botão que este componente desenha.
  musicUrl?: string;
  // Presente só quando quem está vendo é o DONO (ver GalaxiaVivaView.tsx:
  // `selected.relation === "owner"`) — controla se o botão "escolher
  // música" (mini-formulário) aparece. Ausente: só o botão de play (se já
  // houver musicUrl) é mostrado, nunca o de editar. Este componente não
  // sabe COMO isso é persistido (PATCH, endpoint, etc.) — só chama e
  // espera a Promise resolver/rejeitar, mesma filosofia de `since`.
  onSaveMusicUrl?: (url: string) => Promise<void>;
};

// Mesmo padrão de tipo mínimo de MusicPlayer.tsx/LaunchMusicPlayer.tsx —
// nunca importa o tipo real de react-youtube, só os métodos de fato usados.
type MinimalYouTubePlayer = {
  playVideo: () => void;
  pauseVideo: () => void;
};

type Star = {
  x: number;
  y: number;
  r: number;
  baseAlpha: number;
  speed: number;
  phase: number;
  color: string;
  bornAt: number | null;
  appearDelay: number;
  // Vagar orgânico ao redor de (x, y) — nunca uma posição fixa, mas nunca
  // viajando pela tela nem colidindo com outras (ver render(): aplicado
  // como um pequeno deslocamento em px somado à posição-base, não uma
  // reescrita dela). wanderSpeedX/Y deliberadamente diferentes (não o
  // mesmo valor) para o caminho resultante ser um Lissajous simples —
  // orgânico, nunca um círculo perfeito nem sincronizado com outra
  // estrela, e ainda assim só duas chamadas de seno/cosseno por estrela
  // por frame (mesmo custo de ordem de grandeza que o twinkle abaixo).
  wanderRadius: number;
  wanderSpeedX: number;
  wanderSpeedY: number;
  wanderPhaseX: number;
  wanderPhaseY: number;
};

type Duracao = { dias: number; horas: number; min: number; seg: number };

function pad2(n: number): string {
  return (n < 10 ? "0" : "") + n;
}

function calcularDuracao(inicio: Date, agora: Date): Duracao {
  const ms = Math.max(0, agora.getTime() - inicio.getTime());
  const totalSeg = Math.floor(ms / 1000);
  return {
    dias: Math.floor(totalSeg / 86400),
    horas: Math.floor((totalSeg % 86400) / 3600),
    min: Math.floor((totalSeg % 3600) / 60),
    seg: totalSeg % 60,
  };
}

// PRNG determinístico — a mesma "semente" sempre gera a mesma estrela
// (mesma família de lib/galaxyStars.ts, só que com uma semente numérica
// direta em vez de hash de string, já que aqui a "identidade" de uma
// estrela é simplesmente sua posição no dia).
function mulberry32(seed: number): () => number {
  let s = seed;
  return function random() {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function gerarEstrela(index: number): Star {
  const r = mulberry32(index * 9973 + 7);
  const colorRoll = r();
  const color = colorRoll < 0.8 ? "244,246,252" : colorRoll < 0.94 ? "255,255,255" : "222,230,250";
  const sizeRoll = r();
  // Ponto fino e nítido, não bola de luz — a maioria minúscula (expoente
  // > 1 empurra sizeRoll pra perto de 0), poucas um pouco maiores. Sem
  // camada de halo separada (ver render()): é só isto + shadowBlur que dão
  // o respiro, por isso a faixa em si já precisa ser bem mais fina do que
  // antes.
  const size = 0.5 + Math.pow(sizeRoll, 2.2) * 1.4;
  return {
    x: 0.06 + r() * 0.88,
    y: 0.1 + r() * 0.76,
    r: size,
    baseAlpha: 0.6 + r() * 0.4,
    speed: 0.4 + r() * 0.9,
    phase: r() * Math.PI * 2,
    color,
    bornAt: null, // preenchido no momento em que a estrela entra em cena
    appearDelay: 0,
    // Raio pequeno (poucos px) — vagar visível mas sempre contido perto da
    // origem, nunca atravessando a tela. Velocidades baixas e diferentes
    // entre si (nunca a mesma) para o movimento parecer lento e orgânico,
    // nunca um giro mecânico.
    wanderRadius: 3 + r() * 9,
    wanderSpeedX: 0.05 + r() * 0.09,
    wanderSpeedY: 0.05 + r() * 0.09,
    wanderPhaseX: r() * Math.PI * 2,
    wanderPhaseY: r() * Math.PI * 2,
  };
}

function easeOutCubic(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

const fmtData = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "long", year: "numeric" });
const fmtHora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit", hour12: false });

function formatarDesde(d: Date): string {
  return `${fmtData.format(d)} às ${fmtHora.format(d)}`;
}

export default function GalaxiaViva({ since, className = "", musicUrl, onSaveMusicUrl }: GalaxiaVivaProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<Star[]>([]);
  const diasAtuaisRef = useRef(0);
  const pointerRef = useRef({ x: 0, y: 0 });

  const [displayDias, setDisplayDias] = useState(0);
  const [relogio, setRelogio] = useState({ horas: 0, min: 0, seg: 0 });
  const [srResumo, setSrResumo] = useState("");

  const musicPlayerRef = useRef<MinimalYouTubePlayer | null>(null);
  const [musicPlaying, setMusicPlaying] = useState(false);
  // true quando o próprio player do YouTube reporta erro (embed
  // desabilitado pelo dono do vídeo, removido, restrito por idade/região,
  // etc. — ver onError abaixo) — nunca deixa o botão em tela depois disso,
  // já que clicar nele não faria mais nada.
  const [musicError, setMusicError] = useState(false);

  const musicVideoId = useMemo(
    () => (musicUrl ? extractYouTubeVideoId(musicUrl) : null),
    [musicUrl]
  );

  // Reinicia o estado do player sempre que o vídeo muda (ex.: o dono troca
  // de experiência selecionada no ExperiencePicker de GalaxiaVivaView, cada
  // uma com seu próprio link) — nunca herda "tocando"/"erro" de um vídeo
  // anterior. Ajustado DURANTE o render (padrão oficial do React para
  // "resetar estado quando uma prop muda"), não num useEffect — um setState
  // síncrono no corpo de um efeito encadearia uma re-renderização extra
  // evitável (react-hooks/set-state-in-effect).
  const [lastMusicVideoId, setLastMusicVideoId] = useState(musicVideoId);
  if (musicVideoId !== lastMusicVideoId) {
    setLastMusicVideoId(musicVideoId);
    setMusicPlaying(false);
    setMusicError(false);
  }

  function toggleMusic() {
    if (!musicPlayerRef.current) return;

    if (musicPlaying) {
      musicPlayerRef.current.pauseVideo();
      setMusicPlaying(false);
    } else {
      musicPlayerRef.current.playVideo();
      setMusicPlaying(true);
    }
  }

  // Mini-formulário "escolher música" — o dono cola/troca/remove o link
  // sem sair desta tela. musicFormValue só é inicializado ao ABRIR o
  // formulário (openMusicForm), nunca a cada render: reabrir sempre parte
  // do valor atualmente salvo (musicUrl), nunca de um rascunho velho de
  // uma abertura anterior.
  const [musicFormOpen, setMusicFormOpen] = useState(false);
  const [musicFormValue, setMusicFormValue] = useState("");
  const [musicFormError, setMusicFormError] = useState("");
  const [musicFormSaving, setMusicFormSaving] = useState(false);

  function openMusicForm() {
    setMusicFormValue(musicUrl ?? "");
    setMusicFormError("");
    setMusicFormOpen(true);
  }

  async function handleSaveMusic() {
    const trimmed = musicFormValue.trim();
    if (trimmed && !isValidYouTubeUrl(trimmed)) {
      setMusicFormError("Esse link não parece ser de um vídeo do YouTube (watch, youtu.be ou shorts).");
      return;
    }

    setMusicFormSaving(true);
    setMusicFormError("");
    try {
      await onSaveMusicUrl?.(trimmed);
      setMusicFormOpen(false);
    } catch {
      setMusicFormError("Não foi possível salvar agora. Tente novamente.");
    } finally {
      setMusicFormSaving(false);
    }
  }

  // Recalcula do zero sempre que `since` muda (ex.: componente reutilizado
  // para outra experiência) — nunca acumula estado de uma instância
  // anterior.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion =
      typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const duracaoInicial = calcularDuracao(since, new Date());
    diasAtuaisRef.current = duracaoInicial.dias;

    function atualizarResumoAcessivel() {
      setSrResumo(
        `${diasAtuaisRef.current.toLocaleString("pt-BR")} dias desde ${formatarDesde(since)}. ` +
          "Uma nova estrela nasce a cada dia que passa, ao vivo."
      );
    }
    atualizarResumoAcessivel();

    const stars: Star[] = [];
    for (let i = 0; i < diasAtuaisRef.current; i++) {
      const s = gerarEstrela(i);
      s.appearDelay = (i / Math.max(1, diasAtuaisRef.current)) * (reduceMotion ? 0 : 2.2);
      stars.push(s);
    }
    starsRef.current = stars;

    function nascerNovaEstrela(novoTotal: number) {
      const novo = gerarEstrela(novoTotal - 1);
      novo.appearDelay = 0;
      novo.bornAt = performance.now();
      starsRef.current.push(novo);
    }

    let clockIntervalId: number | undefined;
    function iniciarRelogioAoVivo() {
      function tick() {
        const d = calcularDuracao(since, new Date());
        if (d.dias !== diasAtuaisRef.current) {
          if (d.dias > diasAtuaisRef.current) nascerNovaEstrela(d.dias);
          diasAtuaisRef.current = d.dias;
          setDisplayDias(diasAtuaisRef.current);
          atualizarResumoAcessivel();
        }
        setRelogio({ horas: d.horas, min: d.min, seg: d.seg });
      }
      tick();
      clockIntervalId = window.setInterval(tick, 1000);
    }

    let countRafId: number | undefined;
    if (reduceMotion) {
      setDisplayDias(diasAtuaisRef.current);
      iniciarRelogioAoVivo();
    } else {
      let start: number | null = null;
      const duration = 1600;
      const stepCount = (ts: number) => {
        if (start === null) start = ts;
        const p = Math.min(1, (ts - start) / duration);
        setDisplayDias(Math.round(easeOutCubic(p) * diasAtuaisRef.current));
        if (p < 1) {
          countRafId = requestAnimationFrame(stepCount);
        } else {
          iniciarRelogioAoVivo();
        }
      };
      countRafId = requestAnimationFrame(stepCount);
    }

    const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    let W = 0;
    let H = 0;

    function resize() {
      if (!canvas) return;
      const rect = canvas.getBoundingClientRect();
      W = rect.width;
      H = rect.height;
      canvas.width = Math.floor(W * dpr);
      canvas.height = Math.floor(H * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    function handleMouseMove(e: MouseEvent) {
      const rect = canvas!.getBoundingClientRect();
      pointerRef.current = {
        x: ((e.clientX - rect.left) / rect.width - 0.5) * 2,
        y: ((e.clientY - rect.top) / rect.height - 0.5) * 2,
      };
    }
    canvas.addEventListener("mousemove", handleMouseMove);

    type ShootingStar = { x: number; y: number; ang: number; born: number; life: number };
    let shootingStar: ShootingStar | null = null;
    function maybeSpawnShootingStar() {
      if (reduceMotion || shootingStar) return;
      if (Math.random() < 0.006) {
        const sx = Math.random() * W * 0.55 + W * 0.08;
        const sy = Math.random() * H * 0.28;
        const ang = Math.PI * 0.2 + Math.random() * 0.18;
        shootingStar = { x: sx, y: sy, ang, born: performance.now(), life: 850 + Math.random() * 450 };
      }
    }

    let t0: number | null = null;
    let renderRafId: number;
    function render(ts: number) {
      if (t0 === null) t0 = ts;
      const t = (ts - t0) / 1000;
      ctx!.clearRect(0, 0, W, H);

      const driftX = reduceMotion ? 0 : Math.sin(t * 0.02) * 5;
      const driftY = reduceMotion ? 0 : Math.cos(t * 0.017) * 3.5;
      const parX = reduceMotion ? 0 : pointerRef.current.x * 6;
      const parY = reduceMotion ? 0 : pointerRef.current.y * 4;

      const stars = starsRef.current;
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        const localAge = s.bornAt !== null ? (ts - s.bornAt) / 1000 : t - s.appearDelay;
        const appearP = reduceMotion ? 1 : Math.min(1, Math.max(0, localAge / 0.7));
        if (appearP <= 0) continue;

        const isNewest = i === stars.length - 1;
        let birthFlare = 0;
        if (s.bornAt !== null && !reduceMotion) {
          const sinceBirth = (ts - s.bornAt) / 1000;
          birthFlare = Math.max(0, 1 - sinceBirth / 1.6);
        }

        // Brilho contínuo, nunca só de entrada — roda pra sempre a cada
        // frame, cada estrela no seu próprio ritmo (speed/phase já vêm
        // fixos por estrela de gerarEstrela). appearP (acima) só controla
        // o fade-in do nascimento; depois de ~0.7s ele fica em 1 e para de
        // interferir aqui.
        const twinkle = reduceMotion ? 1 : 0.68 + 0.32 * Math.sin(t * s.speed + s.phase);
        const pulse = isNewest && !reduceMotion ? 0.9 + 0.1 * Math.sin(t * 1.7) : 1;
        const alpha = s.baseAlpha * twinkle * appearP * pulse;

        // Vagar orgânico: deslocamento pequeno (px) ao redor da posição-base
        // (s.x*W, s.y*H), nunca substituindo-a — por isso soma, nunca
        // recalcula x/y. Desligado com reduceMotion, igual ao resto do
        // movimento do componente.
        const wanderX = reduceMotion ? 0 : s.wanderRadius * Math.cos(t * s.wanderSpeedX + s.wanderPhaseX);
        const wanderY = reduceMotion ? 0 : s.wanderRadius * Math.sin(t * s.wanderSpeedY + s.wanderPhaseY);

        const depth = s.r / 3.3;
        const px = s.x * W + (parX + driftX) * depth + wanderX;
        const py = s.y * H + (parY + driftY) * depth + wanderY;
        const radius = Math.max(0.35, s.r * pulse);

        // Um único círculo preenchido + shadowBlur — nunca um halo grande
        // em radialGradient nem faísca em cruz: é isso que mantém a
        // estrela um ponto fino e nítido em vez de bola/mancha de luz. O
        // "respiro" vem inteiramente do shadowBlur, não do raio do círculo
        // em si (por isso birthFlare não infla `radius` acima, só o blur
        // abaixo).
        const fillAlpha = Math.min(1, alpha + birthFlare * 0.4);
        const shadowAlpha = Math.min(1, fillAlpha + 0.15);
        const shadowBlur = radius * (isNewest ? 1.6 : 0.7) + radius * 2.5 * birthFlare;

        ctx!.save();
        ctx!.shadowBlur = shadowBlur;
        ctx!.shadowColor = `rgba(${s.color},${shadowAlpha})`;
        ctx!.fillStyle = `rgba(${s.color},${fillAlpha})`;
        ctx!.beginPath();
        ctx!.arc(px, py, radius, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.restore();
      }

      maybeSpawnShootingStar();
      if (shootingStar) {
        const age = ts - shootingStar.born;
        const p = age / shootingStar.life;
        if (p >= 1) {
          shootingStar = null;
        } else {
          const len = 130;
          const travel = p * (W * 0.42);
          const hx = shootingStar.x + Math.cos(shootingStar.ang) * travel;
          const hy = shootingStar.y + Math.sin(shootingStar.ang) * travel;
          const tx = hx - Math.cos(shootingStar.ang) * len;
          const ty = hy - Math.sin(shootingStar.ang) * len;
          const grad = ctx!.createLinearGradient(tx, ty, hx, hy);
          grad.addColorStop(0, "rgba(244,239,228,0)");
          grad.addColorStop(1, `rgba(244,239,228,${0.9 * (1 - p)})`);
          ctx!.strokeStyle = grad;
          ctx!.lineWidth = 1.4;
          ctx!.beginPath();
          ctx!.moveTo(tx, ty);
          ctx!.lineTo(hx, hy);
          ctx!.stroke();
        }
      }

      renderRafId = requestAnimationFrame(render);
    }
    renderRafId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousemove", handleMouseMove);
      if (clockIntervalId !== undefined) window.clearInterval(clockIntervalId);
      if (countRafId !== undefined) cancelAnimationFrame(countRafId);
      cancelAnimationFrame(renderRafId);
    };
  }, [since]);

  return (
    <div
      className={`galaxia-viva relative h-full w-full overflow-hidden rounded-[30px] border ${fraunces.variable} ${cormorant.variable} ${className}`}
      style={{
        background: "radial-gradient(ellipse 90% 80% at 50% 38%, #0b0f1e, #05060d 78%)",
        borderColor: "rgba(150, 165, 205, 0.16)",
        boxShadow: "0 50px 120px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.03)",
        color: "#f2eee3",
        fontFamily: `var(--gv-font-cormorant), "Iowan Old Style", Georgia, serif`,
      }}
    >
      <canvas ref={canvasRef} aria-hidden="true" className="absolute inset-0 block h-full w-full" />

      {musicVideoId && !musicError && (
        // Player invisível (1x1, controls:0) — mesma técnica de
        // MusicPlayer.tsx/LaunchMusicPlayer.tsx. autoplay SEMPRE 0: só toca
        // a partir de um clique real no botão abaixo, nunca sozinho.
        // loop+playlist=próprio id é o truque documentado da IFrame API
        // para repetir um único vídeo (já usado em LaunchMusicPlayer.tsx).
        <div className="pointer-events-none absolute -left-250 -top-250 h-px w-px overflow-hidden opacity-0">
          <YouTube
            videoId={musicVideoId}
            opts={{
              width: "1",
              height: "1",
              playerVars: {
                autoplay: 0,
                controls: 0,
                playsinline: 1,
                rel: 0,
                loop: 1,
                playlist: musicVideoId,
              },
            }}
            onReady={(event) => {
              musicPlayerRef.current = event.target;
            }}
            onError={() => {
              // Vídeo com embed desabilitado/removido/restrito — nunca
              // deixa um botão de play em tela que não faria nada.
              setMusicError(true);
              setMusicPlaying(false);
            }}
          />
        </div>
      )}

      {(onSaveMusicUrl || (musicVideoId && !musicError)) && (
        <div className="pointer-events-auto absolute bottom-4 right-4 z-20 flex items-center gap-2">
          {musicVideoId && !musicError && (
            <button
              type="button"
              onClick={toggleMusic}
              aria-label={musicPlaying ? "Pausar música" : "Tocar música"}
              aria-pressed={musicPlaying}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-black/40 text-lg text-white backdrop-blur-xl transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-300"
            >
              <span aria-hidden="true">{musicPlaying ? "⏸" : "▶️"}</span>
            </button>
          )}

          {onSaveMusicUrl && (
            <button
              type="button"
              onClick={openMusicForm}
              aria-label="Escolher música da Galáxia Viva"
              className="flex h-11 w-11 items-center justify-center rounded-full border border-white/15 bg-black/40 text-lg text-white backdrop-blur-xl transition hover:bg-white/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-300"
            >
              <span aria-hidden="true">🎵</span>
            </button>
          )}
        </div>
      )}

      {musicFormOpen && (
        <div className="pointer-events-auto absolute bottom-[76px] right-4 z-30 w-72 max-w-[calc(100%-2rem)] rounded-2xl border border-white/15 bg-black/70 p-4 backdrop-blur-xl">
          <label className="text-xs font-semibold uppercase tracking-[0.14em] text-white/70">
            Música da Galáxia Viva
          </label>
          <input
            type="url"
            value={musicFormValue}
            onChange={(event) => {
              setMusicFormValue(event.target.value);
              setMusicFormError("");
            }}
            placeholder="https://www.youtube.com/watch?v=..."
            className="mt-2 w-full rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-sm text-white outline-none placeholder:text-white/30 focus:border-yellow-300"
          />
          {musicFormError && <p className="mt-2 text-xs text-red-300">{musicFormError}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setMusicFormOpen(false)}
              className="rounded-full px-3 py-1.5 text-xs font-semibold text-white/70 transition hover:text-white"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSaveMusic}
              disabled={musicFormSaving}
              className="rounded-full bg-yellow-300 px-4 py-1.5 text-xs font-semibold text-black transition hover:bg-yellow-200 disabled:opacity-60"
            >
              {musicFormSaving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </div>
      )}

      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 92% 18% at 50% 6%, rgba(3, 4, 9, 0.6) 0%, rgba(3, 4, 9, 0) 88%)",
        }}
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 78% 72% at 50% 48%, transparent 55%, rgba(2, 2, 6, 0.5) 100%)",
        }}
      />

      <header
        aria-hidden="true"
        className="absolute inset-x-0 top-0 z-[2] flex flex-wrap items-center justify-center gap-y-[0.9rem] px-[clamp(1.1rem,4vw,2.4rem)] py-[clamp(1.3rem,3.2vh,2rem)] text-center"
        style={{ columnGap: "clamp(1rem, 3vw, 2.2rem)" }}
      >
        <div className="flex flex-col items-center gap-[0.2em]">
          <span
            className="m-0 text-[clamp(0.72rem,1.3vw,0.9rem)] font-medium tracking-[0.28em] opacity-90"
            style={{
              fontFamily: `var(--gv-font-fraunces), var(--gv-font-cormorant), Georgia, serif`,
              fontVariantCaps: "all-small-caps",
              color: "#ccd0de",
            }}
          >
            Uma galáxia viva
          </span>
        </div>

        <span
          className="hidden self-stretch min-h-[30px] w-px sm:block"
          style={{ background: "linear-gradient(180deg, transparent, rgba(150,165,205,0.16), transparent)" }}
        />

        <div className="flex flex-col items-center gap-[0.2em]">
          <p
            className="m-0 leading-[0.95] text-[clamp(1.7rem,3.6vw,2.5rem)] font-medium tracking-[-0.01em]"
            style={{
              fontFamily: `var(--gv-font-fraunces), Georgia, serif`,
              fontVariantNumeric: "tabular-nums lining-nums",
              backgroundImage: "linear-gradient(150deg, #7d8296 8%, #ffffff 45%, #ccd0de 78%)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
              filter: "drop-shadow(0 0 14px rgba(255, 255, 255, 0.12))",
            }}
          >
            {displayDias.toLocaleString("pt-BR")}
          </p>
          <p
            className="m-0 text-[clamp(0.72rem,1.3vw,0.85rem)] italic"
            style={{ color: "#9aa0b4" }}
          >
            dias
          </p>
        </div>

        <span
          className="hidden self-stretch min-h-[30px] w-px sm:block"
          style={{ background: "linear-gradient(180deg, transparent, rgba(150,165,205,0.16), transparent)" }}
        />

        <div className="flex flex-col items-center gap-[0.2em]">
          <p
            className="m-0 flex items-baseline justify-center gap-[0.35em] text-[clamp(0.95rem,1.9vw,1.25rem)] font-medium"
            style={{ fontFamily: `var(--gv-font-fraunces), Georgia, serif`, fontVariantNumeric: "tabular-nums", color: "#ffffff" }}
          >
            <span
              className="mr-[0.55em] inline-block h-[7px] w-[7px] animate-[gv-pulse-dot_1.8s_ease-in-out_infinite] self-center rounded-full motion-reduce:animate-none"
              style={{ background: "#ffffff", boxShadow: "0 0 8px 1px rgba(255, 255, 255, 0.55)" }}
            />
            <span>{pad2(relogio.horas)}</span>
            <span className="ml-[0.15em] text-[0.42em] font-normal italic" style={{ color: "#9aa0b4" }}>
              h
            </span>
            <span className="font-normal opacity-55" style={{ color: "#9aa0b4" }}>
              :
            </span>
            <span>{pad2(relogio.min)}</span>
            <span className="ml-[0.15em] text-[0.42em] font-normal italic" style={{ color: "#9aa0b4" }}>
              min
            </span>
            <span className="font-normal opacity-55" style={{ color: "#9aa0b4" }}>
              :
            </span>
            <span>{pad2(relogio.seg)}</span>
            <span className="ml-[0.15em] text-[0.42em] font-normal italic" style={{ color: "#9aa0b4" }}>
              s
            </span>
          </p>
          <p
            className="m-0 text-[clamp(0.62rem,1.1vw,0.72rem)] opacity-75"
            style={{ fontVariantCaps: "all-small-caps", letterSpacing: "0.14em", color: "#9aa0b4" }}
          >
            tempo vivido, em tempo real
          </p>
        </div>

        <span
          className="hidden self-stretch min-h-[30px] w-px sm:block"
          style={{ background: "linear-gradient(180deg, transparent, rgba(150,165,205,0.16), transparent)" }}
        />

        <div className="flex flex-col items-center gap-[0.2em]">
          <span
            className="m-0 text-[clamp(0.64rem,1.2vw,0.78rem)]"
            style={{ fontFamily: `var(--gv-font-fraunces), Georgia, serif`, fontVariantCaps: "all-small-caps", letterSpacing: "0.16em", color: "#9aa0b4" }}
          >
            desde{" "}
            <time dateTime={since.toISOString()} style={{ fontVariantNumeric: "tabular-nums", color: "#ccd0de", opacity: 0.95 }}>
              {formatarDesde(since)}
            </time>
          </span>
        </div>
      </header>

      <p className="sr-only">{srResumo}</p>
    </div>
  );
}
