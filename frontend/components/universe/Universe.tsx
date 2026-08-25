"use client";

import UniverseEngine from "./UniverseEngine";

// Fundo decorativo genérico usado hoje em Landing, Login, Register e
// Dashboard (DashboardShell) — continua um componente de zero props.
// Fase 1 (Universe Engine): a montagem do Canvas/Scene que existia direto
// aqui foi extraída para UniverseEngine.tsx, reutilizável por Minha
// Galáxia/Galáxia Viva mais adiante; `<UniverseEngine />` sem argumentos
// renderiza exatamente o mesmo Canvas+Scene de antes desta mudança — sem
// CameraRig, sem ShootingStars, sem estrelas de memória — então esta
// função continua produzindo a mesma saída visual/funcional de sempre.
export default function Universe() {
  return (
    <div className="absolute inset-0 -z-10">
      <UniverseEngine />
    </div>
  );
}
