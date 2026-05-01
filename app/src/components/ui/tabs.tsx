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
    <BaseTabs.List activateOnFocus className="relative mb-6 flex gap-1.5 overflow-x-auto">
      {tabs.map((tab) => (
        <BaseTabs.Tab
          className={cn(
            "relative z-0 flex shrink-0 cursor-pointer items-center gap-2 whitespace-nowrap rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
            "rounded-full text-muted-foreground hover:bg-muted hover:text-foreground",
            "data-[active]:bg-primary data-[active]:text-primary-foreground",
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
                  ? "bg-primary-foreground/15 text-primary-foreground"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {tab.count}
            </span>
          )}
        </BaseTabs.Tab>
      ))}
      <BaseTabs.Indicator className="hidden" />
    </BaseTabs.List>
  </BaseTabs.Root>
);

type LinkTab = { href: string; label: string; active: boolean; count?: number };

export const LinkTabs = ({ tabs, className }: { tabs: LinkTab[]; className?: string }) => (
  <div className={cn("mb-6 flex gap-1.5 overflow-x-auto", className)}>
    {tabs.map((t) => (
      <Link
        key={t.href}
        href={t.href}
        className={cn(
          "relative z-0 flex shrink-0 items-center gap-2 whitespace-nowrap rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
          "rounded-full text-muted-foreground hover:bg-muted hover:text-foreground",
          t.active && "border border-border bg-background text-foreground",
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
      </Link>
    ))}
  </div>
);
