"use client";

import { Stars } from "@react-three/drei";

import UniverseEngine from "@/components/universe/UniverseEngine";

// "use client" é obrigatório aqui: page.tsx (Server Component) não pode
// importar @react-three/drei/UniverseEngine direto — dá erro de build
// ("k.createContext is not a function") por rodarem em contexto de
// servidor durante a coleta de dados da página. Mesma receita de
// components/launch/ComingSoonView.tsx (shootingStars + uma camada extra
// de <Stars> para um céu mais denso/brilhante que o padrão de Scene.tsx),
// só isolada num componente cliente para poder ser usada em app/page.tsx.

// Posições fixas (nunca Math.random() em render) — evita qualquer
// divergência servidor/cliente na hidratação. Reaproveita a classe .star +
// @keyframes twinkle que já existem em globals.css (mesma usada no ponto
// pulsante de GalaxiaViva.tsx), nunca uma segunda animação inventada. Esta
// camada em CSS puro é a garantia visual de "estrelas brilhando": nunca
// depende do WebGL estar disponível/performático no navegador de quem
// visita, ao contrário do <Stars> 3D abaixo (que continua, só como reforço
// de profundidade).
const SPARKLES = [
  { top: "8%", left: "12%", size: 5, delay: "0s", duration: "3.2s" },
  { top: "15%", left: "82%", size: 4, delay: "0.4s", duration: "2.6s" },
  { top: "22%", left: "45%", size: 4, delay: "1.1s", duration: "3.8s" },
  { top: "30%", left: "68%", size: 5, delay: "0.8s", duration: "3s" },
  { top: "38%", left: "6%", size: 4, delay: "1.6s", duration: "2.8s" },
  { top: "45%", left: "90%", size: 5, delay: "0.2s", duration: "3.4s" },
  { top: "52%", left: "25%", size: 4, delay: "2s", duration: "3.1s" },
  { top: "58%", left: "55%", size: 5, delay: "0.6s", duration: "2.9s" },
  { top: "64%", left: "14%", size: 4, delay: "1.3s", duration: "3.6s" },
  { top: "70%", left: "78%", size: 4, delay: "0.9s", duration: "3.3s" },
  { top: "76%", left: "35%", size: 5, delay: "1.8s", duration: "2.7s" },
  { top: "83%", left: "60%", size: 4, delay: "0.3s", duration: "3.5s" },
  { top: "90%", left: "20%", size: 4, delay: "1.4s", duration: "3s" },
  { top: "12%", left: "30%", size: 4, delay: "2.2s", duration: "2.5s" },
  { top: "95%", left: "85%", size: 5, delay: "0.7s", duration: "3.7s" },
  { top: "5%", left: "60%", size: 4, delay: "1.5s", duration: "2.9s" },
  { top: "48%", left: "8%", size: 5, delay: "1.9s", duration: "3.2s" },
  { top: "62%", left: "95%", size: 4, delay: "0.5s", duration: "2.6s" },
];

export default function LandingUniverse() {
  return (
    <>
      <UniverseEngine shootingStars>
        <Stars radius={140} depth={60} count={7000} factor={7} saturation={0} fade speed={1.4} />
      </UniverseEngine>

      {SPARKLES.map((sparkle, index) => (
        <span
          key={index}
          className="star absolute rounded-full bg-white"
          style={{
            top: sparkle.top,
            left: sparkle.left,
            width: sparkle.size,
            height: sparkle.size,
            animationDuration: sparkle.duration,
            animationDelay: sparkle.delay,
            boxShadow: "0 0 10px 3px rgba(255,255,255,.9), 0 0 20px 6px rgba(250,204,21,.35)",
          }}
        />
      ))}
    </>
  );
}
