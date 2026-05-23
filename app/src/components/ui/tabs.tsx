import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type Tab = { value: string; label: string; count?: number; icon?: LucideIcon };

const tabListClassName = "flex gap-1.5 overflow-x-auto";
const tabClassName =
  "inline-flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-md px-3.5 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2";
const tabCountClassName = "rounded px-1.5 py-0.5 text-xs font-semibold leading-none";
const tabIconClassName = "size-3.5";

const surfaceClass = {
  active: "bg-primary text-primary-foreground shadow-sm",
  inactive: "text-muted-foreground hover:bg-muted hover:text-foreground",
  countActive: "bg-primary-foreground/15 text-primary-foreground",
  countInactive: "bg-muted text-muted-foreground",
  focus: "focus-visible:ring-ring focus-visible:ring-offset-background",
};

const getTabClassName = ({ active, className }: { active: boolean; className?: string }) =>
  cn(
    tabClassName,
    surfaceClass.focus,
    active ? surfaceClass.active : surfaceClass.inactive,
    className,
  );

const getTabCountClassName = ({ active }: { active: boolean }) =>
  cn(tabCountClassName, active ? surfaceClass.countActive : surfaceClass.countInactive);

const TabContent = ({
  active,
  count,
  icon: Icon,
  label,
}: {
  active: boolean;
  count?: number;
  icon?: LucideIcon;
  label: string;
}) => (
  <>
    {Icon && <Icon className={tabIconClassName} />}
    <span>{label}</span>
    {count !== undefined && <span className={getTabCountClassName({ active })}>{count}</span>}
  </>
);

interface TabsProps {
  readonly tabs: Tab[];
  readonly value: string;
  readonly onChange: (value: string) => void;
}

export const Tabs = ({ tabs, value, onChange }: TabsProps) => (
  <BaseTabs.Root onValueChange={(v) => onChange(v as string)} value={value}>
    <BaseTabs.List activateOnFocus className={tabListClassName}>
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
  <div className={cn(tabListClassName, className)}>
    {tabs.map((t) => (
      <Link
        aria-current={t.active ? "page" : undefined}
        key={t.href}
        to={t.href}
        className={getTabClassName({ active: t.active })}
      >
        <TabContent active={t.active} count={t.count} icon={t.icon} label={t.label} />
      </Link>
    ))}
  </div>
);
