"use client";

import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import Link from "next/link";
import { cn } from "@/lib/cn";

type Tab = { value: string; label: string; count?: number };

interface TabsProps {
  readonly tabs: Tab[];
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export const Tabs = ({ tabs, value, onChange }: TabsProps) => (
  <BaseTabs.Root onValueChange={(v) => onChange(v as string)} value={value}>
    <BaseTabs.List
      activateOnFocus
      className="mb-6 flex gap-1 overflow-x-auto border-b border-border"
    >
      {tabs.map((tab) => (
        <BaseTabs.Tab
          className={cn(
            "relative z-0 flex shrink-0 cursor-pointer items-center gap-2 whitespace-nowrap rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
            "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
            "data-[selected]:bg-accent data-[selected]:text-foreground",
          )}
          key={tab.value}
          value={tab.value}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span
              className={cn(
                "rounded-full px-1.5 py-0.5 text-xs",
                value === tab.value
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {tab.count}
            </span>
          )}
        </BaseTabs.Tab>
      ))}
      <BaseTabs.Indicator className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary transition-[left,width] duration-300 ease-[cubic-bezier(0.65,0,0.35,1)]" />
    </BaseTabs.List>
  </BaseTabs.Root>
);

/* Link-based tabs for server-navigated tab shells (collection detail). */
type LinkTab = { href: string; label: string; active: boolean; count?: number };

export const LinkTabs = ({ tabs, className }: { tabs: LinkTab[]; className?: string }) => (
  <div className={cn("mb-6 flex gap-1 overflow-x-auto border-b border-border", className)}>
    {tabs.map((t) => (
      <Link
        key={t.href}
        href={t.href}
        className={cn(
          "relative z-0 flex shrink-0 items-center gap-2 whitespace-nowrap rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
          "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
          t.active && "bg-accent text-foreground",
        )}
      >
        {t.label}
        {t.count !== undefined && (
          <span
            className={cn(
              "rounded-full px-1.5 py-0.5 text-xs",
              t.active ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground",
            )}
          >
            {t.count}
          </span>
        )}
        {t.active && (
          <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary" />
        )}
      </Link>
    ))}
  </div>
);
