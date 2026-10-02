import { getAccessToken } from "./session";

const DEFAULT_API_URL = "http://localhost:8001/api/v1";

export const API_BASE_URL = import.meta.env?.VITE_API_URL || DEFAULT_API_URL;
export const WS_BASE_URL = import.meta.env?.VITE_WS_URL || "ws://localhost:8001/ws";

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

export async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
}

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getAccessToken();
  if (token && path !== "/auth/login") headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message = payload?.error?.message || (typeof payload === "object" && payload !== null && "detail" in payload
      ? JSON.stringify(payload.detail)
      : String(payload));
    throw new Error(message || `Erreur API ${response.status}`);
  }

  return payload as T;
}
