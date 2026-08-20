import { api } from "./api";

// Exactly what GET /api/experiences/themes/ returns — apps.experiences.
// serializers.ThemeSerializer. `name` here is the authoritative display
// name (the backend controls which themes exist, their name, and whether
// they're active); how each code actually looks is a frontend-only concern
// — see lib/themeRegistry.ts.
export type ActiveTheme = {
  code: string;
  name: string;
  features: Record<string, unknown>;
};

// Public (no auth required), only ever returns active themes, already
// ordered by sort_order. The frontend never hardcodes a second list of
// which themes are selectable — this is the only source.
export async function fetchActiveThemes(): Promise<ActiveTheme[]> {
  const response = await api.get<ActiveTheme[]>("/experiences/themes/");
  return response.data;
}
