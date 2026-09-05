"use client";

import { useCallback } from "react";
import type { RootState } from "@react-three/fiber";

// Sem isto, uma perda de contexto WebGL (troca de GPU do laptop, o
// navegador liberando memória de vídeo sob pressão, um crash do processo
// de GPU) fica PERMANENTE: o evento `webglcontextlost` só é recuperável se
// alguém chamar `event.preventDefault()` nele — é assim que a própria
// especificação WebGL decide se vale a pena tentar restaurar o contexto ou
// desistir de vez (ver MDN: "By default, a WebGL context is not
// restorable"). Sem esse listener, o canvas fica preto/quebrado até um
// reload inteiro da página — o suspeito mais provável por trás do aviso
// "THREE.WebGLRenderer: Context Lost" observado durante o scroll da
// experiência.
//
// Um só hook para os dois <Canvas> do produto (EarthCanvas na abertura,
// GalaxyChapter no fechamento) — nunca duas cópias divergentes da mesma
// lógica, mesmo raciocínio que motivou consolidar a extração de video id
// do YouTube em lib/youtube.ts.
export function useWebglContextRecovery(label: string) {
  return useCallback(
    (state: RootState) => {
      const canvas = state.gl.domElement;

      canvas.addEventListener("webglcontextlost", (event) => {
        event.preventDefault();
        // Diagnóstico deliberado: isto não deveria acontecer em uso normal,
        // e não existe hoje nenhum serviço de log de frontend (Sentry etc.)
        // para reportar isto de outro jeito.
        console.warn(`[${label}] WebGL context lost — tentando restaurar.`);
      });

      canvas.addEventListener("webglcontextrestored", () => {
        console.warn(`[${label}] WebGL context restaurado.`);
      });
    },
    [label]
  );
}
