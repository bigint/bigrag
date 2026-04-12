"use client";

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

type NavSection = {
  label: string;
  items: { href: string; label: string; icon: typeof BookOpen }[];
};

const SECTIONS: NavSection[] = [
  {
    label: "Library",
    items: [
      { href: "/overview", label: "Overview", icon: LayoutDashboard },
      { href: "/collections", label: "Collections", icon: BookOpen },
      { href: "/playground", label: "Playground", icon: Sparkles },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/api-keys", label: "API Keys", icon: KeyRound },
      { href: "/users", label: "Admins", icon: Users },
      { href: "/webhooks", label: "Webhooks", icon: Webhook },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

const isActive = (pathname: string, href: string) => {
  if (href === "/overview") return pathname === "/overview" || pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
};

export const Sidebar = () => {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-svh w-60 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-card)]">
      <div className="flex h-14 items-center px-4 border-b border-[var(--color-border)]">
        <Link href="/overview" className="focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] rounded-md">
          <Logo size="sm" />
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {SECTIONS.map((section) => (
          <div key={section.label} className="mb-5 last:mb-0">
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-widest text-[var(--color-muted-foreground)]">
              {section.label}
            </div>
            <ul className="flex flex-col gap-0.5">
              {section.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        "text-[var(--color-muted-foreground)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-muted)]",
                        active &&
                          "bg-[var(--color-accent)] text-[var(--color-accent-foreground)] hover:bg-[var(--color-accent)]",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 shrink-0",
                          active
                            ? "text-[var(--color-primary)]"
                            : "text-[var(--color-muted-foreground)] group-hover:text-[var(--color-foreground)]",
                        )}
                      />
                      <span>{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-[var(--color-border)] p-3">
        <UserMenu />
      </div>
    </aside>
  );
};
