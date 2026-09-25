import axios from "axios";

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/auth";

// The refresh endpoint always lives under /api/auth regardless of which
// client (auth, resumes, ...) triggered the 401 — derive it once from
// BASE_URL so every client below can share the same refresh flow.
const AUTH_ROOT = BASE_URL.replace(/\/api\/auth\/?$/, "/api/auth");

let refreshInFlight = null;

/**
 * Builds an axios instance that attaches the JWT access token to every
 * request and, on a 401, does exactly one silent refresh (shared across all
 * clients created by this function) before retrying. Used for both the
 * existing auth client and the resumes client below, so the refresh
 * behaviour from Module 1 is reused rather than duplicated.
 */
function createAuthedClient(baseURL) {
  const client = axios.create({ baseURL });

  client.interceptors.request.use((config) => {
    const access = localStorage.getItem("access");
    if (access) {
      config.headers.Authorization = `Bearer ${access}`;
    }
    return config;
  });

  client.interceptors.response.use(
    (response) => response,
    async (error) => {
      const { config, response } = error;
      if (response?.status === 401 && !config._retried) {
        config._retried = true;
        const refresh = localStorage.getItem("refresh");
        if (!refresh) {
          return Promise.reject(error);
        }
        try {
          if (!refreshInFlight) {
            refreshInFlight = axios
              .post(`${AUTH_ROOT}/token/refresh/`, { refresh })
              .finally(() => {
                refreshInFlight = null;
              });
          }
          const { data } = await refreshInFlight;
          localStorage.setItem("access", data.access);
          config.headers.Authorization = `Bearer ${data.access}`;
          return client(config);
        } catch (refreshError) {
          localStorage.removeItem("access");
          localStorage.removeItem("refresh");
          localStorage.removeItem("user");
          window.location.href = "/login";
          return Promise.reject(refreshError);
        }
      }
      return Promise.reject(error);
    }
  );

  return client;
}

const api = createAuthedClient(BASE_URL);

// Same host as the auth API, different path — used by resumeApi.js.
export const resumesApi = createAuthedClient(BASE_URL.replace(/\/api\/auth\/?$/, "/api/resumes"));

// Same host again, used by analysisApi.js.
export const analysisApi = createAuthedClient(BASE_URL.replace(/\/api\/auth\/?$/, "/api/analysis"));

// Same host again, used by assistantApi.js.
export const assistantApi = createAuthedClient(BASE_URL.replace(/\/api\/auth\/?$/, "/api/assistant"));

// Same host again, used by historyApi.js.
export const historyApi = createAuthedClient(BASE_URL.replace(/\/api\/auth\/?$/, "/api/history"));

export default api;
