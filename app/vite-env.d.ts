/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BIGRAG_URL?: string;
  readonly VITE_SHOW_ROUTER_DEVTOOLS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@fontsource-variable/outfit";
