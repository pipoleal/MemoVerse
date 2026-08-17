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

  music: {
    provider: "none",
    url: "",
  },

  published: false,
};