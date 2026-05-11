/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RAG_COMPUTER_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@fontsource-variable/outfit";
