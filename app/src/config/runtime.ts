type RuntimeConfig = {
  RAG_COMPUTER_URL?: string;
};

declare global {
  interface Window {
    __RAG_COMPUTER_APP_CONFIG__?: RuntimeConfig;
  }
}

const trimSlash = (value: string) => value.replace(/\/+$/, "");

const runtimeUrl =
  typeof window === "undefined" ? undefined : window.__RAG_COMPUTER_APP_CONFIG__?.RAG_COMPUTER_URL;

export const ragComputerApiUrl = trimSlash(
  runtimeUrl || import.meta.env.VITE_RAG_COMPUTER_URL || "http://localhost:4000",
);

export const apiUrl = (path: string) => `${ragComputerApiUrl}/${path.replace(/^\/+/, "")}`;
