type GoogleFilesParams = {
  readonly pageToken: string;
  readonly parentId: string;
  readonly query: string;
};

type OptionalCollectionParams = {
  readonly collection?: string;
};

type GoogleSyncJobsParams = {
  readonly sourceId?: string;
};

type WindowDaysParams = {
  readonly windowDays: number;
};

type CollectionNameParams = {
  readonly name: string;
};

type ChatDetailParams = {
  readonly id: string | null;
};

type DocumentParams = {
  readonly collection: string;
  readonly id: string;
};

type DocumentListParams = {
  readonly collection: string;
  readonly status?: string;
};

type BatchStatusParams = {
  readonly collection: string;
  readonly ids: string;
};

type UploadSessionParams = {
  readonly collection: string;
  readonly id: string | null;
};

export const queryKeys = {
  auth: {
    all: () => ["auth"] as const,
    setupStatus: () => ["auth", "setup-status"] as const,
    session: () => ["auth", "session"] as const,
  },
  apiKeys: () => ["api-keys"] as const,
  backups: () => ["backups"] as const,
  access: {
    logs: (filters: Record<string, unknown>) => ["access", "logs", filters] as const,
    overview: ({ windowDays }: WindowDaysParams) => ["access", "overview", { windowDays }] as const,
  },
  audit: {
    recent: () => ["audit", "recent"] as const,
  },
  mcpServers: () => ["mcp-servers"] as const,
  webhooks: () => ["webhooks"] as const,
  embeddingPresets: () => ["embedding-presets"] as const,
  preferences: () => ["preferences"] as const,
  instanceSettings: () => ["instance-settings"] as const,
  connectors: {
    googleConfig: () => ["connectors", "google", "config"] as const,
    googleAccount: () => ["connectors", "google", "account"] as const,
    googleFilesRoot: () => ["connectors", "google", "files"] as const,
    googleFiles: ({ pageToken, parentId, query }: GoogleFilesParams) =>
      ["connectors", "google", "files", { pageToken, parentId, query }] as const,
    googleSources: ({ collection }: OptionalCollectionParams = {}) =>
      ["connectors", "google", "sources", { collection: collection ?? "all" }] as const,
    googleSyncJobs: ({ sourceId }: GoogleSyncJobsParams = {}) =>
      ["connectors", "google", "sync-jobs", { sourceId: sourceId ?? "all" }] as const,
  },
  chat: {
    list: () => ["chat", "list"] as const,
    detail: ({ id }: ChatDetailParams) => ["chat", "detail", { id }] as const,
  },
  collections: {
    all: () => ["collections"] as const,
    one: ({ name }: CollectionNameParams) => ["collections", "detail", { name }] as const,
    stats: ({ name }: CollectionNameParams) => ["collections", "stats", { name }] as const,
  },
  documents: {
    list: ({ collection, status }: DocumentListParams) =>
      ["documents", "list", { collection, ...(status ? { status } : {}) }] as const,
    one: ({ collection, id }: DocumentParams) =>
      ["documents", "detail", { collection, id }] as const,
    chunks: ({ collection, id }: DocumentParams) =>
      ["documents", "chunks", { collection, id }] as const,
    batchStatus: ({ collection, ids }: BatchStatusParams) =>
      ["documents", "batch-status", { collection, ids }] as const,
    uploadSession: ({ collection, id }: UploadSessionParams) =>
      ["documents", "upload-session", { collection, id }] as const,
  },
  platform: {
    stats: () => ["platform", "stats"] as const,
    readiness: () => ["platform", "readiness"] as const,
    embeddingModels: () => ["platform", "embedding-models"] as const,
  },
  usage: ({ windowDays }: WindowDaysParams) => ["usage", { windowDays }] as const,
} as const;
