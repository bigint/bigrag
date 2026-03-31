"use client";

import {
  Database,
  Key,
  LayoutGrid,
  LogOut,
  Search,
  Settings,
  TrendingUp,
  Users
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Logo } from "@/components/logo";
import { logout } from "@/lib/api";
import { clearAuth, getUser } from "@/lib/auth-store";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/", icon: LayoutGrid, label: "Dashboard" },
  { href: "/collections", icon: Database, label: "Collections" },
  { href: "/query", icon: Search, label: "Query" },
  { href: "/metrics", icon: TrendingUp, label: "Metrics" },
  { href: "/api-keys", icon: Key, label: "API Keys" },
  { href: "/settings", icon: Settings, label: "Settings" }
] as const;

const ADMIN_ITEMS = [{ href: "/users", icon: Users, label: "Users" }] as const;

export const Sidebar = () => {
  const pathname = usePathname();
  const router = useRouter();
  const user = getUser();

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // ignore errors
    }
    clearAuth();
    router.replace("/login");
  };

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-56 flex-col border-r border-border bg-bg">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-border px-5">
        <Logo size={28} />
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

        {user?.role === "admin" && (
          <>
            <div className="my-2 border-t border-border" />
            {ADMIN_ITEMS.map(({ href, label, icon: Icon }) => {
              const isActive = pathname.startsWith(href);
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
          </>
        )}
      </nav>

      <div className="border-t border-border px-4 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[13px] font-medium text-text">
              {user?.display_name ?? "—"}
            </p>
            <p className="text-[11px] capitalize text-text-dim">
              {user?.role ?? ""}
            </p>
          </div>
          <button
            aria-label="Sign out"
            className="shrink-0 rounded-md p-1.5 text-text-muted transition-colors hover:bg-bg-hover hover:text-text"
            onClick={handleLogout}
            type="button"
          >
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </aside>
  );
};
