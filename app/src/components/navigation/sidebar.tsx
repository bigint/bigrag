import { cn, Sheet } from "@atelier/ui";
import { Link, useRouterState } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BookOpen,
  Cloud,
  Cpu,
  Database,
  FlaskConical,
  HardDrive,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Plug,
  Receipt,
  Settings,
  Webhook,
} from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { UserMenu } from "./user-menu";

interface NavItem {
  readonly href: string;
  readonly label: string;
  readonly icon: LucideIcon;
  readonly admin?: boolean;
}

interface NavGroup {
  readonly label: string;
  readonly items: readonly NavItem[];
}

const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/overview", icon: LayoutDashboard, label: "Overview" },
      { href: "/collections", icon: BookOpen, label: "Collections" },
      { href: "/models", icon: Cpu, label: "Models" },
      { href: "/chat", icon: MessageSquare, label: "Chat" },
      { admin: true, href: "/evals", icon: FlaskConical, label: "Evals" },
    ],
  },
  {
    label: "Interfaces",
    items: [
      { href: "/mcp", icon: Plug, label: "MCP" },
      { admin: true, href: "/api-keys", icon: KeyRound, label: "API Keys" },
      { admin: true, href: "/webhooks", icon: Webhook, label: "Webhooks" },
      { admin: true, href: "/connectors", icon: Cloud, label: "Connectors" },
    ],
  },
  {
    label: "Observability",
    items: [
      { admin: true, href: "/access-logs", icon: Activity, label: "Access Logs" },
      { admin: true, href: "/usage", icon: Receipt, label: "Usage" },
      { admin: true, href: "/audit", icon: ListChecks, label: "Audit" },
    ],
  },
  {
    label: "Administration",
    items: [
      { admin: true, href: "/backups", icon: Archive, label: "Backups" },
      { admin: true, href: "/data-storage", icon: HardDrive, label: "Data Storage" },
      { admin: true, href: "/vector-storage", icon: Database, label: "Vector Storage" },
      { admin: true, href: "/settings", icon: Settings, label: "Settings" },
    ],
  },
];

const getSidebarNavGroups = (role: string) =>
  NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.admin || role === "admin"),
  })).filter((group) => group.items.length > 0);

const isSidebarItemActive = (pathname: string, href: string) => {
  if (href === "/overview") return pathname === "/overview" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
};

const SidebarBody = ({ onNavigate, role }: { onNavigate?: () => void; role: string }) => {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const groups = getSidebarNavGroups(role);

  return (
    <div className="flex h-full w-full flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-4">
        <Logo />
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {groups.map((group, index) => (
          <section
            aria-label={group.label}
            className={cn("space-y-0.5", index > 0 && "mt-4 border-border/70 border-t pt-3")}
            key={group.label}
          >
            <div className="px-2.5 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
              {group.label}
            </div>
            {group.items.map((item) => {
              const active = isSidebarItemActive(pathname, item.href);
              const Icon = item.icon;
              return (
                <Link
                  to={item.href}
                  key={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={onNavigate}
                  className={cn(
                    "flex h-8 items-center gap-2.5 rounded-md px-2.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "bg-background text-foreground"
                      : "text-muted-foreground hover:bg-background hover:text-foreground",
                  )}
                >
                  <Icon className="size-3.5" />
                  <span>{item.label}</span>
                </Link>
              );
            })}
          </section>
        ))}
      </nav>

      <div className="shrink-0">
        <UserMenu />
      </div>
    </div>
  );
};

export const Sidebar = ({ role }: { role: string }) => (
  <aside className="hidden h-[calc(100dvh-1rem)] w-60 shrink-0 overflow-hidden rounded-md border border-border bg-muted lg:flex">
    <SidebarBody role={role} />
  </aside>
);

export const MobileSidebar = ({
  onClose,
  open,
  role,
}: {
  onClose: () => void;
  open: boolean;
  role: string;
}) => {
  return (
    <Sheet
      backdropClassName="lg:hidden"
      className="lg:hidden"
      onClose={onClose}
      open={open}
      side="left"
      title="Navigation"
    >
      <SidebarBody onNavigate={onClose} role={role} />
    </Sheet>
  );
};
