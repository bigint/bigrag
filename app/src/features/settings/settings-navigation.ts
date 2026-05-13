import type { LucideIcon } from "lucide-react";
import {
  Database,
  FileStack,
  HardDrive,
  History,
  Layers,
  ListChecks,
  Lock,
  MessageCircle,
  Plug,
  Receipt,
  Search,
  Server,
  Timer,
  UserRound,
  Webhook,
} from "lucide-react";

type SettingsNavItem = {
  readonly value: string;
  readonly label: string;
  readonly description: string;
  readonly icon: LucideIcon;
};

type SettingsNavGroup = {
  readonly label: string;
  readonly items: readonly SettingsNavItem[];
};

export const DEFAULT_SETTINGS_TAB = "account";

export const SETTINGS_NAV_GROUPS: readonly SettingsNavGroup[] = [
  {
    label: "Personal",
    items: [
      {
        value: "account",
        label: "Account",
        description: "Profile, password, and active sessions for your operator login.",
        icon: UserRound,
      },
    ],
  },
  {
    label: "Platform",
    items: [
      {
        value: "server",
        label: "System health",
        description: "Live readiness of Postgres, Redis, vector store, and embeddings.",
        icon: Server,
      },
      {
        value: "security",
        label: "Security",
        description: "Browser, cookie, proxy, and outbound network policies.",
        icon: Lock,
      },
      {
        value: "backups",
        label: "Backups",
        description: "S3-compatible destination for readable full-instance exports.",
        icon: History,
      },
    ],
  },
  {
    label: "Data",
    items: [
      {
        value: "storage",
        label: "Storage",
        description: "Binary storage for local disk, S3, and MinIO deployments.",
        icon: HardDrive,
      },
      {
        value: "vector_store",
        label: "Vector store",
        description: "Vector backend selection, cloud credentials, and indexes.",
        icon: Database,
      },
      {
        value: "ingestion",
        label: "Ingestion",
        description: "Document upload, conversion, OCR, and worker controls.",
        icon: FileStack,
      },
      {
        value: "retention",
        label: "Retention",
        description: "Operational log retention policies.",
        icon: Timer,
      },
    ],
  },
  {
    label: "Runtime",
    items: [
      {
        value: "queue",
        label: "Queue",
        description: "Queue backpressure and ingestion job limits.",
        icon: Layers,
      },
      {
        value: "search",
        label: "Search",
        description: "Query caches, collection caches, and embedding concurrency.",
        icon: Search,
      },
      {
        value: "chat",
        label: "Chat",
        description: "Default chat provider behavior and model context budgets.",
        icon: MessageCircle,
      },
      {
        value: "webhooks",
        label: "Webhooks",
        description: "Webhook limits, delivery timeouts, and retry cadence.",
        icon: Webhook,
      },
      {
        value: "connectors",
        label: "Connectors",
        description: "OAuth credentials for external data source connectors.",
        icon: Plug,
      },
    ],
  },
  {
    label: "Observability",
    items: [
      {
        value: "usage",
        label: "Usage & cost",
        description: "Aggregated request volume, token usage, and spend.",
        icon: Receipt,
      },
      {
        value: "audit",
        label: "Audit log",
        description: "Administrator activity trail across the instance.",
        icon: ListChecks,
      },
    ],
  },
] as const;

export const SETTINGS_NAV_ITEMS = SETTINGS_NAV_GROUPS.flatMap((group) => group.items);

const SETTINGS_TAB_VALUES = new Set(SETTINGS_NAV_ITEMS.map((item) => item.value));

export const isSettingsTab = (value: string | undefined): value is string =>
  Boolean(value && SETTINGS_TAB_VALUES.has(value));

export const getSettingsTab = (requestedTab: string | undefined): string =>
  isSettingsTab(requestedTab) ? requestedTab : DEFAULT_SETTINGS_TAB;

export const getSettingsNavItem = (tab: string): SettingsNavItem =>
  SETTINGS_NAV_ITEMS.find((item) => item.value === tab) ?? SETTINGS_NAV_ITEMS[0];

export const settingsSectionLabel = (value: string): string => {
  const group = SETTINGS_NAV_GROUPS.find((candidate) =>
    candidate.items.some((item) => item.value === value),
  );
  const item = getSettingsNavItem(value);
  return group ? `${group.label} / ${item.label}` : item.label;
};
