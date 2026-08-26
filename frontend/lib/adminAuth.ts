import { api } from "./api";

// Shape of GET /api/auth/me/ (apps.accounts.views.me.MeView). The JWT
// itself never carries any of this (LoginView/RefreshView are the plain
// SimpleJWT views, no custom claims), so this is a real network call, not
// a token decode.
//
// is_admin (Etapa 9B.6) is the ONLY field the frontend should use to
// decide admin access — it's already the full decision the backend makes
// (is_superuser OR the MEMOVERSE_ADMIN_EMAIL account), computed by the
// same apps.accounts.permissions.is_production_admin() that also gates
// /api/ops/9b4/* server-side. is_superuser is still returned for
// transparency, but nothing in the frontend should branch on it directly.
export type Me = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_superuser: boolean;
  is_admin: boolean;
};

export async function fetchMe(): Promise<Me> {
  const response = await api.get<Me>("/auth/me/");
  return response.data;
}
