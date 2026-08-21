import axios from "axios";
import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from "./storage";

const baseURL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

export const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach access token for authenticated requests
api.interceptors.request.use((config) => {
  try {
    const token = getAccessToken();
    if (token && config && config.headers) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
  } catch (e) {
    // swallow storage errors
  }

  return config;
});

// Simple concurrency-safe refresh handling
let refreshPromise: Promise<any> | null = null;

async function doRefresh() {
  const refresh = getRefreshToken();
  if (!refresh) throw new Error("no_refresh_token");

  // Use a plain axios instance to avoid interceptors
  const client = axios.create({ baseURL, headers: { "Content-Type": "application/json" } });
  const resp = await client.post("/auth/refresh/", { refresh });

  const data = resp.data;
  if (data.access) {
    const newAccess = data.access;
    const newRefresh = data.refresh ?? refresh;
    saveTokens(newAccess, newRefresh);
  }

  return data;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (!originalRequest) return Promise.reject(error);

    const status = error.response ? error.response.status : null;
    const isAuthEndpoint = originalRequest.url && originalRequest.url.includes("/auth/");

    if (status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = doRefresh().finally(() => {
            refreshPromise = null;
          });
        }

        await refreshPromise;

        const access = getAccessToken();
        if (access) {
          originalRequest.headers = originalRequest.headers || {};
          originalRequest.headers["Authorization"] = `Bearer ${access}`;
        }

        return api(originalRequest);
      } catch (e) {
        // Refresh failed — the stored tokens are dead (expired, malformed,
        // or belong to a user that no longer exists) and must never be
        // reused, so always clear them: the next request from any page
        // goes out with no Authorization header, exactly like a real
        // anonymous visitor.
        try {
          clearTokens();
        } catch (er) {
          // ignore
        }

        // A hard redirect here is a safety net for pages that assume an
        // authenticated session (dashboard, checkout, admin, resuming an
        // owned draft) — but /experience/new, /e/[slug] and the landing
        // page are explicitly meant to work with zero session at all (see
        // Etapa 10's anonymous draft + claim_token architecture). A leftover
        // dead token from a previous session must never force-redirect a
        // visitor away from those, or every request they make (even to
        // AllowAny endpoints, since JWTAuthentication rejects an invalid
        // Bearer token before permission_classes is ever consulted) would
        // hijack them into /login mid-flow. clearTokens() above already
        // makes the anonymous flow self-heal on its own next request.
        const isAnonymousTolerantPath =
          typeof window !== "undefined" &&
          (window.location.pathname === "/" ||
            window.location.pathname === "/experience/new" ||
            window.location.pathname.startsWith("/e/") ||
            window.location.pathname === "/login" ||
            window.location.pathname === "/register");

        if (typeof window !== "undefined" && !isAnonymousTolerantPath) {
          window.location.href = "/login";
        }

        return Promise.reject(e);
      }
    }

    return Promise.reject(error);
  }
);