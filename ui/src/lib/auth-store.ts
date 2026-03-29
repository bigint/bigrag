const STORAGE_KEY_API_KEY = "bigrag_api_key";
const STORAGE_KEY_URL = "bigrag_url";

const DEFAULT_URL = process.env.NEXT_PUBLIC_BIGRAG_URL || "http://localhost:8080";
const ENV_API_KEY = process.env.NEXT_PUBLIC_BIGRAG_API_KEY || "";

export function getApiKey(): string {
  if (typeof window === "undefined") return ENV_API_KEY;
  return localStorage.getItem(STORAGE_KEY_API_KEY) ?? ENV_API_KEY;
}

export function setApiKey(key: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY_API_KEY, key);
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
