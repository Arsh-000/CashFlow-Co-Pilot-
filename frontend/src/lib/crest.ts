export const API_BASE = "https://web-production-12233.up.railway.app";
export const TOKEN_KEY = "crest_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function formatINR(value: number | string | null | undefined): string {
  const n = Number(value ?? 0);
  if (!isFinite(n)) return "Rs 0";
  return "Rs " + n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    return res;
  }
  return res;
}
