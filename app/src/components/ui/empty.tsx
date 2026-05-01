import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  bordered?: boolean;
  className?: string;
}

export const Empty = ({
  icon,
  title,
  description,
  action,
  bordered = true,
  className,
}: EmptyStateProps) => (
  <div
    className={cn(
      "p-12 text-center",
      bordered && "rounded-3xl border border-border bg-card",
      className,
    )}
  >
    {icon && (
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {icon}
      </div>
    )}
    <h2 className="text-base font-semibold text-foreground">{title}</h2>
    {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);
