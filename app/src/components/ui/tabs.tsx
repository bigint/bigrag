"use client";

import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";

type TabSurface = "default" | "inverse";
type Tab = { value: string; label: string; count?: number; icon?: LucideIcon };

const tabListClassName = "flex gap-1.5 overflow-x-auto";
const tabClassName =
  "inline-flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-full px-3.5 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2";
const tabCountClassName = "rounded-full px-1.5 py-0.5 text-xs font-semibold leading-none";
const tabIconClassName = "size-3.5";

const surfaceClasses: Record<
  TabSurface,
  {
    active: string;
    inactive: string;
    countActive: string;
    countInactive: string;
    focus: string;
  }
> = {
  default: {
    active: "bg-primary text-primary-foreground shadow-sm",
    inactive: "text-muted-foreground hover:bg-muted hover:text-foreground",
    countActive: "bg-primary-foreground/15 text-primary-foreground",
    countInactive: "bg-muted text-muted-foreground",
    focus: "focus-visible:ring-ring focus-visible:ring-offset-background",
  },
  inverse: {
    active: "bg-primary-foreground text-primary shadow-sm",
    inactive:
      "text-primary-foreground/70 hover:bg-primary-foreground/10 hover:text-primary-foreground",
    countActive: "bg-primary/10 text-primary",
    countInactive: "bg-primary-foreground/10 text-primary-foreground/70",
    focus: "focus-visible:ring-primary-foreground/70 focus-visible:ring-offset-primary",
  },
};

const getTabClassName = ({
  active,
  className,
  surface = "default",
}: {
  active: boolean;
  className?: string;
  surface?: TabSurface;
}) =>
  cn(
    tabClassName,
    surfaceClasses[surface].focus,
    active ? surfaceClasses[surface].active : surfaceClasses[surface].inactive,
    className,
  );

const getTabCountClassName = ({
  active,
  surface = "default",
}: {
  active: boolean;
  surface?: TabSurface;
}) =>
  cn(
    tabCountClassName,
    active ? surfaceClasses[surface].countActive : surfaceClasses[surface].countInactive,
  );

const TabContent = ({
  active,
  count,
  icon: Icon,
  label,
  surface,
}: {
  active: boolean;
  count?: number;
  icon?: LucideIcon;
  label: string;
  surface?: TabSurface;
}) => (
  <>
    {Icon && <Icon className={tabIconClassName} />}
    <span>{label}</span>
    {count !== undefined && (
      <span className={getTabCountClassName({ active, surface })}>{count}</span>
    )}
  </>
);

interface TabsProps {
  readonly tabs: Tab[];
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export const Tabs = ({ tabs, value, onChange }: TabsProps) => (
  <BaseTabs.Root onValueChange={(v) => onChange(v as string)} value={value}>
    <BaseTabs.List activateOnFocus className={cn(tabListClassName, "mb-6")}>
      {tabs.map((tab) => {
        const active = value === tab.value;
        return (
          <BaseTabs.Tab className={getTabClassName({ active })} key={tab.value} value={tab.value}>
            <TabContent active={active} count={tab.count} icon={tab.icon} label={tab.label} />
          </BaseTabs.Tab>
        );
      })}
      <BaseTabs.Indicator className="hidden" />
    </BaseTabs.List>
  </BaseTabs.Root>
);

type LinkTab = { href: string; label: string; active: boolean; count?: number; icon?: LucideIcon };

export const LinkTabs = ({ tabs, className }: { tabs: LinkTab[]; className?: string }) => (
  <div className={cn(tabListClassName, "mb-6", className)}>
    {tabs.map((t) => (
      <Link
        aria-current={t.active ? "page" : undefined}
        key={t.href}
        href={t.href}
        className={getTabClassName({ active: t.active })}
      >
        <TabContent active={t.active} count={t.count} icon={t.icon} label={t.label} />
      </Link>
    ))}
  </div>
);
