// Fase 2.1 — Etapa 3 contextual por tipo de experiência.
//
// Single source of what InformationStep.tsx renders and what
// ExperienceBuilder.tsx requires before advancing, keyed by experience.type.
// Adding a new experience type (or changing an existing one's questions)
// only ever means editing INFORMATION_STEP_CONFIG below — never touching
// InformationStep.tsx/ExperienceBuilder.tsx themselves, and never an
// `if (type === "...")` chain anywhere.
//
// The 6 ids below mirror TypeStep.tsx's own local list exactly (that file
// is deliberately left untouched — its ids are stable literal strings, not
// worth the risk of exporting/importing across an otherwise-unrelated
// step). If a 7th type is ever added there, it must be added here too, or
// it silently falls back to the "custom" config below (see
// getInformationStepConfig) rather than breaking.
export type ExperienceTypeId =
  | "dating"
  | "marriage"
  | "birthday"
  | "monthiversary"
  | "tribute"
  | "custom";

// Only the Experience keys InformationStep ever reads/writes — each one
// already exists on Experience (types.ts) with this exact name, so a field
// config can index `experience[key]` / `updateExperience({ [key]: value })`
// directly, with no per-type dispatch anywhere.
export type InformationFieldKey =
  | "title"
  | "recipient"
  | "creator"
  | "eventDate"
  | "shortMessage"
  | "contextAnswer";

export type InformationField = {
  key: InformationFieldKey;
  label: string;
  description?: string;
  placeholder?: string;
  component: "input" | "textarea" | "date";
  required: boolean;
  // Only meaningful for component: "textarea".
  rows?: number;
};

export type InformationStepConfig = {
  fields: InformationField[];
};

// The 4 fields every type has always had — same labels/copy as before this
// change, except `recipient`, which a handful of types override (e.g.
// "Homenageado" for tribute) via the `recipient` param.
function baseFields(recipient?: {
  label?: string;
  description?: string;
  placeholder?: string;
}): InformationField[] {
  return [
    {
      key: "title",
      label: "Título da experiência",
      description: "Dê um nome especial para essa experiência.",
      placeholder: "Nosso Pedido de Namoro ❤️",
      component: "input",
      required: true,
    },
    {
      key: "recipient",
      label: recipient?.label ?? "Para quem é?",
      description: recipient?.description ?? "A pessoa que receberá essa experiência.",
      placeholder: recipient?.placeholder ?? "Nome de quem receberá",
      component: "input",
      required: true,
    },
    {
      key: "creator",
      label: "Seu nome",
      description: "Como você gostaria de aparecer na experiência?",
      placeholder: "Seu nome",
      component: "input",
      required: true,
    },
    {
      key: "eventDate",
      label: "Data especial",
      description: "A data que representa esse momento.",
      component: "date",
      required: true,
    },
  ];
}

export const INFORMATION_STEP_CONFIG: Record<ExperienceTypeId, InformationStepConfig> = {
  dating: {
    fields: [
      ...baseFields(),
      {
        key: "shortMessage",
        label: "Como vocês se conheceram?",
        description: "Conte rapidinho como essa história começou.",
        placeholder: "Nos conhecemos em...",
        component: "textarea",
        required: false,
        rows: 3,
      },
      {
        key: "contextAnswer",
        label: "O que você sente por essa pessoa?",
        description: "Isso vai te ajudar a escrever a carta mais pra frente.",
        placeholder: "Eu sinto...",
        component: "textarea",
        required: false,
        rows: 3,
      },
    ],
  },

  marriage: {
    fields: [
      ...baseFields(),
      {
        key: "shortMessage",
        label: "Como começou a história de vocês?",
        description: "Conte rapidinho como essa história começou.",
        placeholder: "Tudo começou quando...",
        component: "textarea",
        required: false,
        rows: 3,
      },
      {
        key: "contextAnswer",
        label: "Por que você quer dar esse próximo passo?",
        description: "Isso vai te ajudar a escrever a carta mais pra frente.",
        placeholder: "Eu quero porque...",
        component: "textarea",
        required: false,
        rows: 3,
      },
    ],
  },

  birthday: {
    fields: [
      ...baseFields(),
      {
        key: "shortMessage",
        label: "Qual a sua relação com essa pessoa?",
        placeholder: "Ex: melhor amiga, irmão, namorado...",
        component: "input",
        required: false,
      },
      {
        key: "contextAnswer",
        label: "O que você mais admira nessa pessoa?",
        component: "textarea",
        required: false,
        rows: 3,
      },
    ],
  },

  monthiversary: {
    fields: [
      ...baseFields(),
      {
        key: "shortMessage",
        label: "Há quanto tempo estão juntos?",
        placeholder: "Ex: 3 meses",
        component: "input",
        required: false,
      },
      {
        key: "contextAnswer",
        label: "Qual momento vocês mais gostam de lembrar?",
        component: "textarea",
        required: false,
        rows: 3,
      },
    ],
  },

  tribute: {
    fields: [
      ...baseFields({
        label: "Homenageado",
        description: "A pessoa que está sendo homenageada.",
        placeholder: "Nome de quem será homenageado",
      }),
      {
        key: "shortMessage",
        label: "Qual a sua relação com essa pessoa?",
        placeholder: "Ex: pai, avó, professor...",
        component: "input",
        required: false,
      },
      {
        key: "contextAnswer",
        label: "Por que essa pessoa é especial para você?",
        component: "textarea",
        required: false,
        rows: 3,
      },
    ],
  },

  // Deliberadamente o único tipo sem contextAnswer — "campos flexíveis, sem
  // presumir o contexto" (não há uma segunda pergunta genérica que faça
  // sentido pra todo mundo aqui). shortMessage mantém exatamente o rótulo/
  // comportamento de antes desta mudança.
  custom: {
    fields: [
      ...baseFields({
        label: "Destinatário",
        description: "A pessoa que receberá essa experiência.",
      }),
      {
        key: "shortMessage",
        label: "Uma mensagem curta",
        description: "Opcional. Uma frase para dar ainda mais personalidade à experiência.",
        placeholder: "Toda estrela tem uma história. A nossa começou aqui...",
        component: "textarea",
        required: false,
        rows: 4,
      },
    ],
  },
};

// Unknown/legacy/empty type (a draft mid-wizard on step 1, or an old value
// that predates some future type change) never errors and never renders an
// empty form — always resolves to a real, complete config. Same fallback
// pattern as lib/themeRegistry.ts's getThemeVisual().
export function getInformationStepConfig(type?: string | null): InformationStepConfig {
  if (type && type in INFORMATION_STEP_CONFIG) {
    return INFORMATION_STEP_CONFIG[type as ExperienceTypeId];
  }
  return INFORMATION_STEP_CONFIG.custom;
}
