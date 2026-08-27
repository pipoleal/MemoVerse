export type MusicProvider =
  | "none"
  | "youtube"
  | "spotify"
  | "apple_music"
  | "external";

export interface MusicSelection {
  provider: MusicProvider;
  url: string;
}

// Fase 2.2: photos carrega uma legenda individual por foto — videos
// continua string[] (mensagens em vídeo ficam para uma fase futura,
// reaproveitando este mesmo shape sem quebrar nada aqui). caption é
// sempre string (nunca undefined), "" representa "sem legenda", mesmo
// padrão de shortMessage/contextAnswer.
export interface PhotoMemory {
  url: string;
  caption: string;
}

export interface Experience {
  type: string;

  theme: string;

  title: string;

  recipient: string;

  creator: string;

  eventDate: string;

  photos: PhotoMemory[];

  videos: string[];

  letter: string;

  shortMessage: string;

  // Fase 2.1: segunda pergunta contextual por tipo de experiência (a
  // primeira é shortMessage) — ver informationStepConfig.ts. Texto livre,
  // sempre opcional, mesmo padrão de shortMessage.
  contextAnswer: string;

  music: MusicSelection;

  // Etapa Galáxia Viva: trilha de fundo tocada SÓ em /dashboard/galaxia-viva
  // (GalaxiaViva.tsx), com botão de play manual — nunca autoplay, nunca a
  // página pública. Campo próprio, separado de `music` acima (aquele toca
  // na experiência pública ao iniciar a jornada e aceita YouTube/Spotify/
  // Apple Music; este é sempre YouTube). "" = sem música, mesmo padrão de
  // shortMessage/contextAnswer.
  galaxyLiveMusicUrl: string;

  published: boolean;
}

export const initialExperience: Experience = {
  type: "",

  theme: "",

  title: "",

  recipient: "",

  creator: "",

  eventDate: "",

  photos: [],

  videos: [],

  letter: "",

  shortMessage: "",

  contextAnswer: "",

  music: {
    provider: "none",
    url: "",
  },

  galaxyLiveMusicUrl: "",

  published: false,
};