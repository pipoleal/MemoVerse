import { api } from "./api";

// Shape of GET /api/auth/me/ (apps.accounts.views.me.MeView) — the only
// place is_superuser is ever exposed to the frontend. The JWT itself never
// carries it (LoginView/RefreshView are the plain SimpleJWT views, no
// custom claims), so this is a real network call, not a token decode.
export type Me = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_superuser: boolean;
};

export async function fetchMe(): Promise<Me> {
  const response = await api.get<Me>("/auth/me/");
  return response.data;
}
