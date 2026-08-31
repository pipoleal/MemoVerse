import { NextRequest, NextResponse } from "next/server";

import { isBeforeLaunch, LAUNCH_AT_UTC_MS } from "./lib/launch";

// Content-Security-Policy via middleware (não next.config.ts) por um motivo
// técnico específico, não por preferência: o App Router injeta os próprios
// scripts inline de bootstrap (`<script>(self.__next_f=...).push(...)</script>`,
// o mecanismo de streaming do RSC payload) em toda página — sem um nonce
// por requisição, script-src sem 'unsafe-inline' bloqueia esses scripts do
// PRÓPRIO Next.js e a hidratação nunca completa (confirmado: com a CSP
// definida estaticamente em next.config.ts, a home carregava em branco e o
// console mostrava "InvariantError: Expected a request ID to be defined
//... self.__next_r"). O Next.js lê o nonce de volta do header
// Content-Security-Policy da resposta e o aplica automaticamente aos seus
// próprios scripts injetados — esse é o mecanismo oficial documentado pelo
// próprio framework para CSP + App Router, não uma CSP genérica copiada.
//
// isDev decide as duas únicas concessões que nunca devem alcançar produção:
// 'unsafe-eval' (Fast Refresh do Turbopack) e o WebSocket de HMR
// (ws://localhost). NODE_ENV=production é automático em `next build`/`next start`.
const isDev = process.env.NODE_ENV !== "production";

// Mesma env var que frontend/lib/api.ts já usa para toda chamada de API —
// nunca hardcoded, para que dev (127.0.0.1:8000) e produção (domínio real
// do backend no Render) funcionem sem editar este arquivo por ambiente.
function backendOrigin(): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";
  try {
    return new URL(apiUrl).origin;
  } catch {
    return "http://127.0.0.1:8000";
  }
}

function buildContentSecurityPolicy(nonce: string): string {
  const backend = backendOrigin();

  const directives: [string, string[]][] = [
    ["default-src", ["'self'"]],

    // 'nonce-...': cobre os scripts inline que o PRÓPRIO Next.js injeta
    // (RSC payload streaming) — ver comentário acima.
    // sdk.mercadopago.com: script injetado dinamicamente por
    // @mercadopago/sdk-js (initMercadoPago(), usado em CardPaymentBlock.tsx)
    // — confirmado no próprio pacote (SDK_MERCADOPAGO_URL =
    // 'https://sdk.mercadopago.com/js/v2'), não é um domínio adivinhado.
    // www.youtube.com: script "iframe_api" que a lib react-youtube injeta
    // (via youtube-player/loadYouTubeIframeApi.js) para controlar o player
    // invisível de MusicPlayer.tsx.
    // 'unsafe-eval' SÓ em dev: exigido pelo Fast Refresh do Turbopack
    // (next dev) — nunca incluído no build de produção.
    [
      "script-src",
      [
        "'self'",
        `'nonce-${nonce}'`,
        "https://sdk.mercadopago.com",
        // http2.mlstatic.com: CDN estático da MercadoLibre (mesmo grupo do
        // Mercado Pago) de onde o Brick de Cartão baixa seu PRÓPRIO bundle
        // (.../op-cho-bricks/build/3.16.0/components/cardPayment.js) —
        // carregado sob demanda só quando a aba "Cartão" é aberta, por
        // isso não aparece com sdk.mercadopago.com no carregamento inicial.
        // Confirmado ao vivo: sem esta entrada, esse .js é bloqueado (visto
        // como 503 na aba Network, mas um fetch() direto no console
        // confirma "Failed to fetch" == bloqueio de CSP, não erro remoto) e
        // Bricks.create() trava para sempre em "Carregando formulário de
        // pagamento...".
        "https://http2.mlstatic.com",
        "https://www.youtube.com",
        // http://www.youtube.com (SÓ dev): youtube-player (biblioteca usada
        // por react-youtube, tanto em MusicPlayer.tsx quanto no novo
        // LaunchMusicPlayer.tsx) escolhe o protocolo do próprio
        // window.location.protocol para o <script> do iframe_api
        // (loadYouTubeIframeApi.js: protocol = location.protocol==='http:'
        // ? 'http:' : 'https:') — em produção (https://memoverse.com.br) o
        // resultado já é sempre "https://www.youtube.com/iframe_api",
        // coberto pela entrada acima; só localhost servido em http://
        // durante `next dev` gera "http://www.youtube.com/iframe_api",
        // bloqueado sem esta entrada (confirmado ao vivo: CSP violation no
        // console, script nunca carrega, player nunca fica pronto).
        ...(isDev ? ["http://www.youtube.com"] : []),
        ...(isDev ? ["'unsafe-eval'"] : []),
      ],
    ],

    // 'unsafe-inline' aqui é o prop `style={{...}}` do React (framer-motion
    // e diversos componentes de experience-view/checkout calculam estilo
    // em runtime — parallax, rotação, cores por composição) — isso compila
    // para o atributo HTML `style="..."`, que style-src bloqueia por
    // padrão sem 'unsafe-inline'. Diferente dos scripts acima, um nonce NÃO
    // resolve este caso: nonces cobrem elementos <script>/<style>, nunca o
    // ATRIBUTO style="..." de um elemento qualquer (isso é regido por
    // style-src-attr, que não tem suporte a nonce por elemento dinâmico
    // prático aqui). Hash também não é viável: os valores são computados
    // dinamicamente a cada render (progresso de scroll/animação), não
    // strings estáticas conhecidas em build time. Risco aceito:
    // 'unsafe-inline' em style-src permite injeção de CSS num XSS
    // hipotético (nunca execução de JavaScript) — script-src permanece
    // protegido por nonce em produção, sem nenhuma das duas exceções.
    ["style-src", ["'self'", "'unsafe-inline'"]],

    [
      "img-src",
      [
        "'self'",
        "data:", // QR code Pix (CheckoutView.tsx: data:image/png;base64,...)
        "blob:", // preview local de foto antes do upload (PhotosStep.tsx: URL.createObjectURL)
        "https://*.r2.cloudflarestorage.com", // fotos da experiência (PhotoMemoryBeat.tsx, <Image unoptimized>)
      ],
    ],

    [
      "media-src",
      [
        "'self'",
        "blob:", // preview local de vídeo antes do upload (VideosStep.tsx: URL.createObjectURL)
        "https://*.r2.cloudflarestorage.com", // vídeos da experiência (VideoMemoryBeat.tsx: <video src>)
      ],
    ],

    // next/font/google (Geist/Geist_Mono, ver app/layout.tsx) self-hospeda
    // os arquivos de fonte em /_next/static/media no build — nenhuma
    // requisição a fonts.gstatic.com acontece em runtime, então 'self'
    // basta.
    ["font-src", ["'self'"]],

    [
      "connect-src",
      [
        "'self'",
        backend, // toda chamada de lib/api.ts (accounts/experiences/payments)
        "https://api.mercadopago.com", // tokenização de cartão / payment_methods / devices/widgets do Brick
        // api.mercadolibre.com (domínio DIFERENTE de api.mercadopago.com,
        // mesma empresa): endpoint de telemetria interna do Brick
        // (POST .../tracks, chamado por dentro do fluxo de
        // "/checkout/api_integration" do SDK). Confirmado ao vivo: sem esta
        // entrada, o Bricks.create() trava para sempre em "Carregando
        // formulário de pagamento..." (a chamada bloqueada pelo CSP faz o
        // init do Brick abortar) — não é apenas um erro de log cosmético.
        "https://api.mercadolibre.com",
        // http2.mlstatic.com também serve o i18n do Brick via fetch
        // (.../cardPayment/index.json) — mesmo CDN do script acima
        // (script-src), mas esta chamada é XHR/fetch, não <script>, por
        // isso precisa estar também aqui.
        "https://http2.mlstatic.com",
        // api-static.mercadopago.com: chamada de configuração dos "secure
        // fields" (campos de número/CVV/validade do cartão, PCI-compliant)
        // feita pelo próprio código do Brick antes de montar o iframe
        // seguro. Confirmado ao vivo: bloqueado sem esta entrada
        // (GET .../secure-fields aparecia como 503; fetch() direto no
        // console confirmou "Failed to fetch" = bloqueio de CSP), causando
        // "TypeError: Cannot read properties of undefined (reading
        // 'message')" dentro do próprio SDK e o formulário nunca
        // aparecendo.
        "https://api-static.mercadopago.com",
        // secure-fields.mercadopago.com também é chamado via fetch/XHR
        // pelo próprio código do Brick (não só como src de iframe, que já
        // está em frame-src) — confirmado ao vivo: um fetch() direto para
        // este domínio continuava bloqueado mesmo depois de liberado em
        // frame-src, e só passou a funcionar após esta entrada aqui.
        "https://secure-fields.mercadopago.com",
        // O upload de mídia (lib/mediaUpload.ts: XMLHttpRequest PUT direto
        // para a URL presignada) é uma chamada XHR, não um <img>/<video> —
        // regida por connect-src, não por img-src/media-src (confirmado
        // testando ao vivo: sem esta entrada, o navegador bloqueia o PUT
        // antes de qualquer byte sair, mesmo com o domínio já liberado em
        // img-src/media-src para exibição).
        "https://*.r2.cloudflarestorage.com",
        ...(isDev ? ["ws://localhost:*", "ws://127.0.0.1:*"] : []), // HMR do Turbopack (next dev)
      ],
    ],

    // Os 3 embeds de música de MusicPlayer.tsx, mais o iframe PCI-compliant
    // dos "secure fields" de cartão do Brick (secure-fields.mercadopago.com
    // — confirmado ao vivo: sem esta entrada, a requisição para montar o
    // iframe do campo de cartão aparecia bloqueada, 503, e o Brick nunca
    // saía do carregamento). Nenhum outro iframe existe no projeto
    // (confirmado por busca em todo o frontend).
    [
      "frame-src",
      [
        "https://www.youtube.com",
        "https://open.spotify.com",
        "https://embed.music.apple.com",
        "https://secure-fields.mercadopago.com",
      ],
    ],

    // Nenhum <object>/<embed> (Flash-like) é usado em lugar nenhum.
    ["object-src", ["'none'"]],
    // Nunca permite <base href> injetado mudar a origem relativa de scripts/links.
    ["base-uri", ["'self'"]],
    // Todo <form> deste app envia para dentro da própria origem (a API é
    // sempre chamada via fetch/axios, nunca via submit de formulário).
    ["form-action", ["'self'"]],
    // Ninguém pode colocar o MemoVerse dentro de um <iframe> de outro site
    // (clickjacking) — equivalente a X-Frame-Options: SAMEORIGIN.
    ["frame-ancestors", ["'self'"]],
  ];

  return directives.map(([key, values]) => `${key} ${values.join(" ")}`).join("; ");
}

export function middleware(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = buildContentSecurityPolicy(nonce);

  // x-nonce: como o App Router (Server Components) sabe qual nonce usar
  // para os próprios scripts injetados — Next.js lê isso automaticamente
  // do header da REQUISIÇÃO durante a renderização, por isso precisa estar
  // aqui, não só na resposta.
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  // Landing temporária de lançamento (ver lib/launch.ts): comparação
  // EXATA de pathname — nunca um prefixo — então só a própria "/" pode
  // disparar isto; /e/[slug], /login, /register, /forgot-password,
  // /dashboard, /checkout, /admin nunca passam por aqui. isBeforeLaunch()
  // usa Date.now() deste processo (servidor/edge), nunca o relógio do
  // navegador de quem está visitando — mesmo que alguém adiante o
  // relógio do próprio computador, esta checagem roda de novo a cada
  // requisição e nunca confia em nada vindo do cliente. Rewrite (não
  // redirect): a URL na barra de endereços continua "/", só o conteúdo
  // servido muda — desaparece sozinho, sem deploy novo, no instante exato
  // em que a hora real passar do lançamento.
  const isRoot = request.nextUrl.pathname === "/";
  const bypass = hasPreviewBypass(request);
  const response =
    isRoot && isBeforeLaunch() && !bypass
      ? NextResponse.rewrite(new URL("/coming-soon", request.url), {
          request: { headers: requestHeaders },
        })
      : NextResponse.next({
          request: { headers: requestHeaders },
        });
  response.headers.set("Content-Security-Policy", csp);

  // Grava o cookie só quando o bypass veio da query string (?preview_key=...)
  // — uma visita já usando o cookie não precisa regravá-lo. httpOnly: nunca
  // legível/gravável por JS de página nenhuma (inclusive um XSS
  // hipotético); sameSite=lax + secure fora de dev: nunca enviado
  // cross-site nem por http puro. Expira sozinho pouco depois do
  // lançamento — não é um mecanismo de acesso permanente, só evita
  // repetir o link secreto a cada visita durante a janela de preview.
  if (bypass === "from-query") {
    response.cookies.set(PREVIEW_COOKIE_NAME, previewSecret() ?? "", {
      httpOnly: true,
      sameSite: "lax",
      secure: !isDev,
      path: "/",
      expires: new Date(LAUNCH_AT_UTC_MS + 24 * 60 * 60 * 1000),
    });
  }

  return response;
}

const PREVIEW_COOKIE_NAME = "mv_preview";

// LAUNCH_PREVIEW_SECRET: variável de servidor só (nunca NEXT_PUBLIC_*, nunca
// commitada) — configurada localmente em frontend/.env.local e, em
// produção, direto no painel do Vercel. Sem ela configurada, o bypass fica
// permanentemente desligado (nunca um valor padrão adivinhável).
function previewSecret(): string | null {
  const value = process.env.LAUNCH_PREVIEW_SECRET;
  return value && value.length > 0 ? value : null;
}

// Permite visitar "/" antes do lançamento sem esperar a hora oficial —
// só para quem tem o link secreto (?preview_key=...) ou já visitou uma vez
// e carrega o cookie resultante. Nunca vaza para o público: sem a env var
// configurada, ?preview_key=qualquer-coisa nunca bate com null.
function hasPreviewBypass(request: NextRequest): "from-query" | "from-cookie" | false {
  const secret = previewSecret();
  if (!secret) return false;

  if (request.nextUrl.searchParams.get("preview_key") === secret) return "from-query";
  if (request.cookies.get(PREVIEW_COOKIE_NAME)?.value === secret) return "from-cookie";
  return false;
}

export const config = {
  // Mesmo padrão do exemplo oficial do Next.js: aplica a todas as rotas,
  // exceto assets estáticos internos (_next/static, _next/image, favicon) —
  // esses já são same-origin e não precisam de um nonce por requisição.
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
