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
        // refresh failed - clear stored tokens and force login
        try {
          clearTokens();
        } catch (er) {
          // ignore
        }

        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }

        return Promise.reject(e);
      }
    }

    return Promise.reject(error);
  }
);