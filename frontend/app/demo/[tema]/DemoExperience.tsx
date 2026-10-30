"use client";

import ExperienceViewer from "@/components/experience-view/ExperienceViewer";
import { initialExperience } from "@/components/experience/types";

// Experiência de demonstração (dados fictícios, sem back-end) para mostrar
// o redesign das 7 telas em cada tema — ver app/demo/[tema]/page.tsx.
export default function DemoExperience({ theme }: { theme: string }) {
  return (
    <ExperienceViewer
      isOwner={false}
      experience={{
        ...initialExperience,
        type: "couple",
        theme,
        title: "O dia em que nosso universo começou",
        recipient: "Marina",
        creator: "Felipe",
        eventDate: "2023-08-12",
        letter:
          "Marina,\nEu ainda lembro de cada detalhe daquela tarde de chuva. Eu só queria um café, e você levou meu guarda-chuva e me deixou sem saída: ou eu te convidava pra conversar, ou ficava molhado. Foi a melhor escolha forçada da minha vida.\n\nDe lá pra cá, a gente construiu um universo inteiro. As viagens, os sábados sem fazer nada, as risadas que ninguém mais entende.\nTe amo.",
        shortMessage:
          "Nos conhecemos em 2023, numa tarde de chuva, na fila de uma cafeteria. Três horas depois, a gente ainda estava lá.",
        contextAnswer: "Cada risada, cada viagem e cada sábado à toa viraram uma estrela.",
        photos: [
          { url: "/textures/earth.jpg", caption: "O dia em que nos conhecemos no café" },
          {
            url: "/brand/memoverse-lockup.png",
            caption: "Por mais linda que a vista fosse, não era nada comparado com a sua beleza",
          },
        ],
        videos: [],
      }}
    />
  );
}
