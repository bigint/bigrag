import { clearClientCache } from "./client";

const STORAGE_KEY_URL = "bigrag_url";
const STORAGE_KEY_SESSION = "bigrag_session_token";
const STORAGE_KEY_USER = "bigrag_user";

const DEFAULT_URL =
  process.env.NEXT_PUBLIC_BIGRAG_URL || "http://localhost:6000";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  role: "admin" | "member";
  created_at: string;
  updated_at: string;
}

export function getBaseUrl(): string {
  if (typeof window === "undefined") return DEFAULT_URL;
  return localStorage.getItem(STORAGE_KEY_URL) || DEFAULT_URL;
}

export function setBaseUrl(url: string): void {
  if (typeof window === "undefined") return;
  if (url) {
    localStorage.setItem(STORAGE_KEY_URL, url);
  } else {
    localStorage.removeItem(STORAGE_KEY_URL);
  }
}

export function getSessionToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(STORAGE_KEY_SESSION) ?? "";
}

export function setSessionToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_SESSION, token);
}

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(STORAGE_KEY_USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setUser(user: AuthUser): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEY_SESSION);
  localStorage.removeItem(STORAGE_KEY_USER);
  clearClientCache();
}

export function isAuthenticated(): boolean {
  return !!getSessionToken();
}
