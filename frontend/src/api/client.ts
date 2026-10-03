import axios from "axios";

export const apiClient = axios.create({
  baseURL: "/api/v1",
});

let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) throw new Error("No refresh token");
  const { data } = await axios.post("/api/v1/auth/refresh", { refresh_token: refreshToken });
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data.access_token;
}

function refreshOnce(): Promise<string> {
  refreshPromise ??= refreshAccessToken().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

/** Seconds until the JWT's `exp`, or null if it can't be read. Decoding only
 * — the server stays the authority on whether a token is valid. */
function secondsUntilExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.exp === "number" ? payload.exp - Date.now() / 1000 : null;
  } catch {
    return null;
  }
}

apiClient.interceptors.request.use(async (config) => {
  let token = localStorage.getItem("access_token");
  // A visit after the 30-minute access token lapsed used to cost a full
  // wasted round trip (request -> 401 -> refresh -> repeat the request), and
  // to a server this far from the school each round trip is hundreds of
  // milliseconds. If we can already see the token is stale, refresh first.
  if (token && localStorage.getItem("refresh_token")) {
    const left = secondsUntilExpiry(token);
    if (left !== null && left < 15) {
      try {
        token = await refreshOnce();
      } catch {
        // Fall through with the old token: the server's 401 and the response
        // interceptor below remain the single place that logs the user out.
      }
    }
  }
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && localStorage.getItem("refresh_token")) {
      original._retry = true;
      try {
        const token = await refreshOnce();
        original.headers.Authorization = `Bearer ${token}`;
        return apiClient(original);
      } catch {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/";
      }
    }
    return Promise.reject(error);
  }
);
