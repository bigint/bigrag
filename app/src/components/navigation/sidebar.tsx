import { Dialog } from "@base-ui/react/dialog";
import { Link, useRouterState } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BookOpen,
  Cpu,
  FlaskConical,
  KeyRound,
  LayoutDashboard,
  MessageSquare,
  Plug,
  Settings,
  Webhook,
} from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { cn } from "@/lib/cn";
import { UserMenu } from "./user-menu";

interface NavItem {
  readonly href: string;
  readonly label: string;
  readonly icon: LucideIcon;
  readonly admin?: boolean;
  readonly separated?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/overview", icon: LayoutDashboard, label: "Overview" },
  { href: "/collections", icon: BookOpen, label: "Collections" },
  { href: "/models", icon: Cpu, label: "Models" },
  { href: "/chat", icon: MessageSquare, label: "Chat" },
  { admin: true, href: "/evals", icon: FlaskConical, label: "Evals" },
  { href: "/mcp", icon: Plug, label: "MCP" },
  { admin: true, href: "/api-keys", icon: KeyRound, label: "API Keys", separated: true },
  { admin: true, href: "/access-logs", icon: Activity, label: "Access Logs" },
  { admin: true, href: "/webhooks", icon: Webhook, label: "Webhooks" },
  { admin: true, href: "/settings", icon: Settings, label: "Settings" },
];

const isActive = (pathname: string, href: string) => {
  if (href === "/overview") return pathname === "/overview" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
};

const SidebarBody = ({ onNavigate, role }: { onNavigate?: () => void; role: string }) => {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const items = NAV_ITEMS.filter((item) => !item.admin || role === "admin");

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-4">
        <Logo />
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
        {items.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <div key={item.href}>
              {item.separated && <div className="my-2 border-t border-border" />}
              <Link
                to={item.href}
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
            </div>
          );
        })}
      </nav>

      <div className="shrink-0">
        <UserMenu />
      </div>
    </div>
  );
};

export const Sidebar = ({ role }: { role: string }) => (
  <aside className="hidden h-full w-60 shrink-0 overflow-hidden rounded-xl border border-border bg-background p-0.5 lg:flex">
    <div className="flex size-full flex-col overflow-hidden rounded-lg bg-muted">
      <SidebarBody role={role} />
    </div>
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
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Backdrop render={<div className="fixed inset-0 z-50 bg-black/50 lg:hidden" />} />
        <Dialog.Popup
          render={
            <div className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-sm flex-col border-r border-border bg-background lg:hidden" />
          }
        >
          <Dialog.Title className="sr-only">Navigation</Dialog.Title>
          <SidebarBody onNavigate={onClose} role={role} />
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
};
