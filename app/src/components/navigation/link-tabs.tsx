import { cn, getTabClassName, TabContent, type TabIcon, type TabSurface } from "@atelier/ui";
import { Link } from "@tanstack/react-router";

type LinkTab = {
  readonly active: boolean;
  readonly count?: number;
  readonly href: string;
  readonly icon?: TabIcon;
  readonly label: string;
};

export const LinkTabs = ({
  className,
  surface = "default",
  tabs,
}: {
  readonly className?: string;
  readonly surface?: TabSurface;
  readonly tabs: readonly LinkTab[];
}) => (
  <div className={cn("flex gap-1.5 overflow-x-auto", className)}>
    {tabs.map((tab) => (
      <Link
        aria-current={tab.active ? "page" : undefined}
        className={getTabClassName({ active: tab.active, surface })}
        key={tab.href}
        to={tab.href}
      >
        <TabContent
          active={tab.active}
          count={tab.count}
          icon={tab.icon}
          label={tab.label}
          surface={surface}
        />
      </Link>
    ))}
  </div>
);
