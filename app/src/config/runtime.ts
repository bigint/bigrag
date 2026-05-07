type RuntimeConfig = {
  BIGRAG_URL?: string;
};

declare global {
  interface Window {
    __BIGRAG_APP_CONFIG__?: RuntimeConfig;
  }
}

const trimSlash = (value: string) => value.replace(/\/+$/, "");

const runtimeUrl =
  typeof window === "undefined" ? undefined : window.__BIGRAG_APP_CONFIG__?.BIGRAG_URL;

export const bigragApiUrl = trimSlash(
  runtimeUrl || import.meta.env.VITE_BIGRAG_URL || "http://localhost:4000",
);

export const apiUrl = (path: string) => `${bigragApiUrl}/${path.replace(/^\/+/, "")}`;
