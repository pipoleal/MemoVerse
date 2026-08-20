"use client";

// Só entra em cena se o próprio RootLayout falhar ao renderizar — por isso
// precisa dos próprios <html>/<body> e evita importar componentes/CSS do
// resto do app (Button, Tailwind, etc.): esses mesmos módulos podem fazer
// parte do que quebrou. Estilo inline de propósito, sem dependência externa.
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="pt-BR">
      <body
        style={{
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "1.5rem",
          backgroundColor: "#020617",
          color: "#ffffff",
          textAlign: "center",
          padding: "1.5rem",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", fontWeight: 600, margin: 0 }}>Algo deu errado.</h1>
        <p style={{ maxWidth: "28rem", fontSize: "0.875rem", color: "rgba(255,255,255,0.6)", margin: 0 }}>
          Não conseguimos carregar o MemoVerse agora. Tente novamente em instantes.
        </p>
        <button
          type="button"
          onClick={reset}
          style={{
            borderRadius: "9999px",
            padding: "1rem 2rem",
            fontWeight: 600,
            backgroundColor: "#facc15",
            color: "#000000",
            border: "none",
            cursor: "pointer",
          }}
        >
          Tentar novamente
        </button>
      </body>
    </html>
  );
}
