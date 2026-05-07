/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BIGRAG_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@fontsource-variable/outfit";
