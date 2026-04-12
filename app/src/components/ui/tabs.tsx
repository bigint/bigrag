"use client";

import Link from "next/link";
import { cn } from "@/lib/cn";

type Tab = { href: string; label: string; active: boolean; count?: number };

export const LinkTabs = ({ tabs, className }: { tabs: Tab[]; className?: string }) => (
  <div className={cn("flex items-center gap-1 overflow-x-auto border-b border-border", className)}>
    {tabs.map((t) => (
      <Link
        key={t.href}
        href={t.href}
        className={cn(
          "relative whitespace-nowrap rounded-t-md px-3 py-2 text-sm font-medium transition-colors",
          "hover:text-foreground",
          t.active ? "text-foreground" : "text-muted-foreground",
        )}
      >
        <span className="inline-flex items-center gap-1.5">
          {t.label}
          {t.count !== undefined && (
            <span className="rounded-full bg-muted px-1.5 py-px text-[10px] tabular-nums">
              {t.count}
            </span>
          )}
        </span>
        {t.active && <span className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-primary" />}
      </Link>
    ))}
  </div>
);
