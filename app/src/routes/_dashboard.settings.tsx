import { createFileRoute, useNavigate } from "@tanstack/react-router";
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
import { useEffect } from "react";
import { AccountTab } from "@/features/settings/tabs/account-tab";
import { AuditTab } from "@/features/settings/tabs/audit-tab";
import { BackupsTab } from "@/features/settings/tabs/backups-tab";
import { ConnectorsTab } from "@/features/settings/tabs/connectors-tab";
import { InstanceSettingsTab } from "@/features/settings/tabs/instance-settings-tab";
import { ServerTab } from "@/features/settings/tabs/server-tab";
import { UsageTab } from "@/features/settings/tabs/usage-tab";
import { cn } from "@/lib/cn";
import type { InstanceSettingGroup } from "@/types/bigrag";

type SettingsSearch = {
  google_error?: string;
  tab?: string;
};

export const Route = createFileRoute("/_dashboard/settings")({
  validateSearch: (search: Record<string, unknown>): SettingsSearch => ({
    google_error: typeof search.google_error === "string" ? search.google_error : undefined,
    tab: typeof search.tab === "string" ? search.tab : undefined,
  }),
  component: () => <SettingsPage />,
});

type NavItem = {
  readonly value: string;
  readonly label: string;
  readonly description: string;
  readonly icon: LucideIcon;
};

type NavGroup = {
  readonly label: string;
  readonly items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
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
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

const settingsTab = (group: InstanceSettingGroup) => () => <InstanceSettingsTab group={group} />;

const COMPONENTS: Record<string, React.FC> = {
  account: AccountTab,
  server: ServerTab,
  security: settingsTab("security"),
  ingestion: settingsTab("ingestion"),
  storage: settingsTab("storage"),
  vector_store: settingsTab("vector_store"),
  queue: settingsTab("queue"),
  search: settingsTab("search"),
  chat: settingsTab("chat"),
  webhooks: settingsTab("webhooks"),
  retention: settingsTab("retention"),
  backups: BackupsTab,
  connectors: ConnectorsTab,
  usage: UsageTab,
  audit: AuditTab,
};

const SettingsPage = () => {
  const navigate = useNavigate();
  const search = Route.useSearch();
  const requestedTab = search.tab;
  const tab = requestedTab && COMPONENTS[requestedTab] ? requestedTab : "account";

  useRedirectLegacyEvalTab(requestedTab, navigate);

  const setTab = (value: string) => {
    navigate({
      to: "/settings",
      search: { ...search, tab: value },
      replace: true,
    });
  };

  const Active = COMPONENTS[tab] ?? AccountTab;
  const active = ALL_ITEMS.find((item) => item.value === tab) ?? ALL_ITEMS[0];
  const ActiveIcon = active.icon;

  return (
    <div className="-mt-6 -mx-4 flex flex-col md:-mx-8 lg:-mx-10 lg:flex-row lg:gap-10">
      <aside className="shrink-0 border-b border-border px-4 py-6 md:px-8 lg:sticky lg:top-0 lg:max-h-dvh lg:w-64 lg:overflow-y-auto lg:border-b-0 lg:border-r lg:py-8 lg:pr-6 lg:pl-10">
        <div className="mb-5">
          <h2 className="text-base font-semibold tracking-normal">Settings</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Instance configuration</p>
        </div>
        <nav className="flex flex-col gap-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-col gap-1">
              <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                {group.label}
              </div>
              <div className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const isActive = item.value === tab;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      aria-current={isActive ? "page" : undefined}
                      onClick={() => setTab(item.value)}
                      className={cn(
                        "flex h-8 items-center gap-2.5 rounded-md px-2 text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        isActive
                          ? "bg-muted text-foreground"
                          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                      )}
                    >
                      <Icon className="size-3.5 shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </aside>

      <section className="min-w-0 flex-1 px-4 py-6 md:px-8 lg:py-8 lg:pl-0 lg:pr-10">
        <header className="mb-6 flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-foreground">
            <ActiveIcon className="size-4" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-semibold leading-tight tracking-normal">{active.label}</h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              {active.description}
            </p>
          </div>
        </header>
        <div>
          <Active />
        </div>
      </section>
    </div>
  );
};

const useRedirectLegacyEvalTab = (
  requestedTab: string | undefined,
  navigate: ReturnType<typeof useNavigate>,
) => {
  useEffect(() => {
    if (requestedTab === "eval") {
      navigate({ to: "/evals", replace: true });
    }
  }, [requestedTab, navigate]);
};
