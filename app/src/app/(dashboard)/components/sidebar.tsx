"use client";

import { Dialog } from "@base-ui/react/dialog";
import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Cpu,
  FlaskConical,
  KeyRound,
  LayoutDashboard,
  Plug,
  Settings,
  Sparkles,
  Webhook,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  { href: "/playground", icon: Sparkles, label: "Playground" },
  { admin: true, href: "/evals", icon: FlaskConical, label: "Evals" },
  { href: "/mcp", icon: Plug, label: "MCP" },
  { admin: true, href: "/api-keys", icon: KeyRound, label: "API Keys", separated: true },
  { admin: true, href: "/webhooks", icon: Webhook, label: "Webhooks" },
  { admin: true, href: "/settings", icon: Settings, label: "Settings" },
];

const isActive = (pathname: string, href: string) => {
  if (href === "/overview") return pathname === "/overview" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
};

const SidebarBody = ({ onNavigate, role }: { onNavigate?: () => void; role: string }) => {
  const pathname = usePathname();
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
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={onNavigate}
                className={cn(
                  "flex h-8 items-center gap-2.5 rounded-full px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active
                    ? "bg-background text-foreground shadow-xs"
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
  <aside className="hidden h-full w-60 shrink-0 overflow-hidden rounded-[24px] border-2 border-border bg-background p-0.5 lg:flex">
    <div className="flex size-full flex-col overflow-hidden rounded-[20px] bg-muted">
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
  const isReduced = useReducedMotion();
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <AnimatePresence>
        {open && (
          <Dialog.Portal>
            <Dialog.Backdrop
              render={
                <motion.div
                  className="fixed inset-0 z-50 bg-black/50 lg:hidden"
                  initial={isReduced ? { opacity: 1 } : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: isReduced ? 0 : 0.15 }}
                />
              }
            />
            <Dialog.Popup
              render={
                <motion.div
                  className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-border bg-background shadow-xl lg:hidden"
                  initial={isReduced ? { x: 0 } : { x: "-100%" }}
                  animate={{ x: 0 }}
                  exit={isReduced ? { opacity: 0 } : { x: "-100%" }}
                  transition={
                    isReduced ? { duration: 0 } : { duration: 0.25, ease: [0.16, 1, 0.3, 1] }
                  }
                />
              }
            >
              <Dialog.Title className="sr-only">Navigation</Dialog.Title>
              <SidebarBody onNavigate={onClose} role={role} />
            </Dialog.Popup>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
};
