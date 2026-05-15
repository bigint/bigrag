import type { LucideIcon } from "lucide-react";
import { Activity, Database, Lock, UserRound } from "lucide-react";
import type { InstanceSettingGroup } from "@/types/bigrag";

export type SettingsTab = "account" | "health" | "security" | "data";

type SettingsNavItem = {
  readonly value: SettingsTab;
  readonly label: string;
  readonly description: string;
  readonly icon: LucideIcon;
};

type SettingsNavGroup = {
  readonly label: string;
  readonly items: readonly SettingsNavItem[];
};

export const DEFAULT_SETTINGS_TAB: SettingsTab = "account";

export const SETTINGS_NAV_GROUPS: readonly SettingsNavGroup[] = [
  {
    items: [
      {
        description: "Profile, password, and active sessions for your operator login.",
        icon: UserRound,
        label: "Account",
        value: "account",
      },
    ],
    label: "Personal",
  },
  {
    items: [
      {
        description: "Readiness for Postgres, Redis, vector storage, and embeddings.",
        icon: Activity,
        label: "Health",
        value: "health",
      },
      {
        description: "Browser access, session policy, outbound URLs, and cache posture.",
        icon: Lock,
        label: "Security",
        value: "security",
      },
      {
        description: "File storage, ingestion, queues, webhooks, and retention.",
        icon: Database,
        label: "Data",
        value: "data",
      },
    ],
    label: "Operate",
  },
] as const;

export const SETTINGS_NAV_ITEMS = SETTINGS_NAV_GROUPS.flatMap((group) => group.items);

const SETTINGS_TAB_VALUES = new Set<SettingsTab>(SETTINGS_NAV_ITEMS.map((item) => item.value));

const SETTINGS_TAB_ALIASES: Readonly<Record<string, SettingsTab>> = {
  ingestion: "data",
  queue: "data",
  retention: "data",
  server: "health",
  storage: "data",
  webhooks: "data",
};

const SETTINGS_FOCUS_GROUPS: Readonly<Record<string, InstanceSettingGroup>> = {
  ingestion: "ingestion",
  queue: "queue",
  retention: "retention",
  security: "security",
  storage: "storage",
  webhooks: "webhooks",
};

export const DATA_SETTINGS_GROUPS: readonly InstanceSettingGroup[] = [
  "storage",
  "ingestion",
  "queue",
  "retention",
  "webhooks",
];

export const isSettingsTab = (value: string | undefined): value is SettingsTab =>
  Boolean(value && SETTINGS_TAB_VALUES.has(value as SettingsTab));

export const getSettingsTab = (requestedTab: string | undefined): SettingsTab => {
  if (isSettingsTab(requestedTab)) return requestedTab;
  return requestedTab
    ? (SETTINGS_TAB_ALIASES[requestedTab] ?? DEFAULT_SETTINGS_TAB)
    : DEFAULT_SETTINGS_TAB;
};

export const getSettingsFocusGroup = (
  requestedTab: string | undefined,
): InstanceSettingGroup | undefined =>
  requestedTab ? SETTINGS_FOCUS_GROUPS[requestedTab] : undefined;

export const getSettingsNavItem = (tab: string): SettingsNavItem =>
  SETTINGS_NAV_ITEMS.find((item) => item.value === getSettingsTab(tab)) ?? SETTINGS_NAV_ITEMS[0];

export const settingsSectionLabel = (value: string): string => {
  const tab = getSettingsTab(value);
  const group = SETTINGS_NAV_GROUPS.find((candidate) =>
    candidate.items.some((item) => item.value === tab),
  );
  const item = getSettingsNavItem(tab);
  return group ? `${group.label} / ${item.label}` : item.label;
};

export const settingsAliasLabel = (value: string): string => {
  const focusGroup = getSettingsFocusGroup(value);
  if (!focusGroup) return settingsSectionLabel(value);
  const labels: Record<InstanceSettingGroup, string> = {
    backups: "Backups",
    chat: "Chat defaults",
    ingestion: "Ingestion",
    queue: "Queue",
    retention: "Retention",
    search: "Embedding and search",
    security: "Security",
    storage: "File storage",
    vector_store: "Vector storage",
    webhooks: "Webhooks",
  };
  return labels[focusGroup];
};
