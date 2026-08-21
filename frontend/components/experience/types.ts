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

export interface Experience {
  type: string;

  theme: string;

  title: string;

  recipient: string;

  creator: string;

  eventDate: string;

  photos: string[];

  videos: string[];

  letter: string;

  shortMessage: string;

  // Fase 2.1: segunda pergunta contextual por tipo de experiência (a
  // primeira é shortMessage) — ver informationStepConfig.ts. Texto livre,
  // sempre opcional, mesmo padrão de shortMessage.
  contextAnswer: string;

  music: MusicSelection;

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

  published: false,
};