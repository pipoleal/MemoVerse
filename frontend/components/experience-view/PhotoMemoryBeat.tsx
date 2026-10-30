"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { motion } from "framer-motion";

import { useInViewport } from "@/lib/useInViewport";
import { fetchPublicExperience, toExperience } from "@/lib/publicExperience";

import MemoryFrame from "./MemoryFrame";

type PhotoMemoryBeatProps = {
  src: string;
  // Fase 2.2: opcional — "" (ou ausente) não reserva nenhum espaço visual,
  // a foto renderiza exatamente como antes desta mudança.
  caption?: string;
  // Posição dentro de photos[] — usada para achar a URL renovada abaixo.
  index: number;
  // Posição/total entre todas as memórias (fotos + vídeos), só para
  // exibição — ver MemoryFrame.tsx.
  memoryNumber: number;
  memoryCount: number;
  onNavigate: (slide: number) => void;
  // Slug público da experiência — só o suficiente para reemitir GET
  // /public/experiences/<slug>/ e pegar uma URL assinada nova caso `src`
  // (assinada no carregamento inicial da página) já tenha expirado quando o
  // visitante finalmente rola até esta foto (carta longa, app trocado no
  // celular, aba em segundo plano...). undefined no modo wizard/preview —
  // lá, sem link público ainda, uma foto que falhar simplesmente continua
  // quebrada (mesmo comportamento de antes desta mudança).
  slug?: string;
};

export default function PhotoMemoryBeat({
  src,
  caption,
  index,
  memoryNumber,
  memoryCount,
  onNavigate,
  slug,
}: PhotoMemoryBeatProps) {
  const sectionRef = useRef<HTMLElement | null>(null);

  const { isInView: isNear } = useInViewport<HTMLElement>(
    { rootMargin: "55% 0px", threshold: 0, once: true },
    sectionRef
  );

  // Renovação da URL assinada expirada — ver comentário de `slug` acima.
  // `currentSrc` começa como a URL original e só é trocada se ela de fato
  // falhar; `hasRetriedRef` garante no máximo uma tentativa por foto (uma
  // segunda falha após a renovação é um problema real, não mais expiração).
  const [currentSrc, setCurrentSrc] = useState(src);
  const hasRetriedRef = useRef(false);

  async function handleImageError() {
    if (hasRetriedRef.current || !slug) return;
    hasRetriedRef.current = true;

    try {
      const fresh = await fetchPublicExperience(slug);
      const renewedUrl = toExperience(fresh).photos[index]?.url;
      if (renewedUrl) setCurrentSrc(renewedUrl);
    } catch {
      // Sem conexão ou slug não encontra mais a experiência — a foto
      // continua quebrada, mesmo estado de antes desta mudança.
    }
  }

  return (
    <MemoryFrame
      ref={sectionRef}
      ariaLabel={`Memória ${memoryNumber + 1} de ${memoryCount}`}
      memoryNumber={memoryNumber}
      memoryCount={memoryCount}
      caption={caption}
      onNavigate={onNavigate}
      isNear={isNear}
    >
      {/* Leve aproximação contínua (Ken Burns), só transform. */}
      <motion.div
        className="absolute inset-0"
        animate={{ scale: [1, 1.05] }}
        transition={{ duration: 11, repeat: Infinity, repeatType: "mirror", ease: "easeInOut" }}
      >
        {/* Fundo: a mesma foto, ampliada e borrada, preenche a moldura
            inteira atrás da versão nítida — é ela que substitui as barras
            pretas numa foto vertical/horizontal que não tem a proporção da
            moldura. Puramente decorativa (aria-hidden). */}
        <Image
          src={currentSrc}
          alt=""
          aria-hidden="true"
          fill
          unoptimized
          sizes="(max-width: 768px) 100vw, 448px"
          className="scale-110 object-cover opacity-80 blur-2xl"
        />

        {/* Primeiro plano: a foto inteira, sem cortar nada (object-contain
            sobre o fundo borrado acima). */}
        <Image
          src={currentSrc}
          alt={caption ? `Memória ${memoryNumber + 1}: ${caption}` : `Memória ${memoryNumber + 1}`}
          fill
          unoptimized
          sizes="(max-width: 768px) 100vw, 448px"
          className="object-contain"
          onError={handleImageError}
        />
      </motion.div>

      <div className="pointer-events-none absolute inset-0 bg-linear-to-t from-black/35 via-transparent to-black/10" />
    </MemoryFrame>
  );
}
