"use client";

import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  KeyRound,
  LayoutDashboard,
  Settings,
  Sparkles,
  Users,
  Webhook,
} from "lucide-react";
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
}

const NAV_ITEMS: NavItem[] = [
  { href: "/overview", icon: LayoutDashboard, label: "Overview" },
  { href: "/collections", icon: BookOpen, label: "Collections" },
  { href: "/playground", icon: Sparkles, label: "Playground" },
  { admin: true, href: "/api-keys", icon: KeyRound, label: "API Keys" },
  { admin: true, href: "/users", icon: Users, label: "Admins" },
  { admin: true, href: "/webhooks", icon: Webhook, label: "Webhooks" },
  { admin: true, href: "/settings", icon: Settings, label: "Settings" },
];

const isActive = (pathname: string, href: string) => {
  if (href === "/overview") return pathname === "/overview" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
};

export const Sidebar = () => {
  const pathname = usePathname();

  let seenAdmin = false;

  return (
    <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border bg-muted/50">
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-4 py-4">
        <Logo />
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
    </aside>
  );
};
