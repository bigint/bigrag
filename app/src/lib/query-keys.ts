export const queryKeys = {
  auth: {
    all: () => ["auth"] as const,
    setupStatus: () => ["auth", "setup-status"] as const,
    session: () => ["auth", "session"] as const,
  },
  apiKeys: () => ["api-keys"] as const,
  access: {
    logs: (filters: Record<string, unknown>) => ["access", "logs", filters] as const,
    overview: (windowDays: number) => ["access", "overview", windowDays] as const,
  },
  mcpServers: () => ["mcp-servers"] as const,
  webhooks: () => ["webhooks"] as const,
  embeddingPresets: () => ["embedding-presets"] as const,
  preferences: () => ["preferences"] as const,
  connectors: {
    googleConfig: () => ["connectors", "google", "config"] as const,
    googleAccount: () => ["connectors", "google", "account"] as const,
    googleFiles: (parentId: string, query: string, pageToken: string) =>
      ["connectors", "google", "files", parentId, query, pageToken] as const,
    googleSources: (collection?: string) =>
      ["connectors", "google", "sources", collection ?? "all"] as const,
    googleSyncJobs: (sourceId?: string) =>
      ["connectors", "google", "sync-jobs", sourceId ?? "all"] as const,
  },
  chat: {
    list: () => ["chat", "list"] as const,
    detail: (id: string | null) => ["chat", "detail", id] as const,
  },
  collections: {
    all: () => ["collections"] as const,
    one: (name: string) => ["collections", name] as const,
    stats: (name: string) => ["collections", name, "stats"] as const,
  },
  documents: {
    list: (collection: string) => ["documents", collection] as const,
    one: (collection: string, id: string) => ["documents", collection, id] as const,
    chunks: (collection: string, id: string) => ["documents", collection, id, "chunks"] as const,
  },
  platform: {
    stats: () => ["platform", "stats"] as const,
    readiness: () => ["platform", "readiness"] as const,
    embeddingModels: () => ["platform", "embedding-models"] as const,
  },
} as const;
