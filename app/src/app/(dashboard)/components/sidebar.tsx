"use client";

import { Dialog } from "@base-ui/react/dialog";
import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Cpu,
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
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { cn } from "@/lib/cn";
import { UserMenu } from "./user-menu";

interface NavItem {
  readonly href: string;
  readonly label: string;
  readonly icon: LucideIcon;
  readonly admin?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/overview", icon: LayoutDashboard, label: "Overview" },
  { href: "/collections", icon: BookOpen, label: "Collections" },
  { href: "/models", icon: Cpu, label: "Models" },
  { href: "/playground", icon: Sparkles, label: "Playground" },
  { href: "/mcp", icon: Plug, label: "MCP" },
  { admin: true, href: "/api-keys", icon: KeyRound, label: "API Keys" },
  { admin: true, href: "/webhooks", icon: Webhook, label: "Webhooks" },
  { admin: true, href: "/settings", icon: Settings, label: "Settings" },
];

const isActive = (pathname: string, href: string) => {
  if (href === "/overview") return pathname === "/overview" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
};

const SidebarBody = ({ onNavigate }: { onNavigate?: () => void }) => {
  const pathname = usePathname();
  let seenAdmin = false;

  return (
    <div className="flex h-full flex-col">
      <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-4">
        <Logo />
        <ThemeToggle />
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {NAV_ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          const prefix =
            item.admin && !seenAdmin ? <div className="my-2 border-t border-border" /> : null;
          if (item.admin) seenAdmin = true;
          return (
            <div key={item.href}>
              {prefix}
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-primary font-medium text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )}
              >
                <Icon className="size-4" />
                {item.label}
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

export const Sidebar = () => (
  <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r border-border bg-muted/50 lg:block">
    <SidebarBody />
  </aside>
);

export const MobileSidebar = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
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
              <SidebarBody onNavigate={onClose} />
            </Dialog.Popup>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
};
