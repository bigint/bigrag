"use client";

import {
  Key,
  LayoutGrid,
  List,
  Lock,
  Settings,
  TrendingUp
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", icon: LayoutGrid, label: "Dashboard" },
  { href: "/vault", icon: Lock, label: "Vault" },
  { href: "/namespaces", icon: List, label: "Namespaces" },
  { href: "/metrics", icon: TrendingUp, label: "Metrics" },
  { href: "/api-keys", icon: Key, label: "API Keys" },
  { href: "/settings", icon: Settings, label: "Settings" }
] as const;

export const Sidebar = () => {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-56 flex-col border-r border-border bg-bg">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-5">
        <div className="flex size-7 items-center justify-center rounded-lg bg-accent">
          <span className="text-xs font-bold text-white">B</span>
        </div>
        <span className="text-sm font-semibold tracking-tight">bigRAG</span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {nav.map(({ href, label, icon: Icon }) => {
          const isActive =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              className={cn(
                "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors",
                isActive
                  ? "bg-bg-hover text-text"
                  : "text-text-muted hover:bg-bg-hover hover:text-text"
              )}
              href={href}
              key={href}
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border px-4 py-3 text-[11px] text-text-dim">
        v0.1.0
      </div>
    </aside>
  );
};
