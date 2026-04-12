import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type Props = {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

export const Empty = ({ icon: Icon, title, description, action, className }: Props) => (
  <div
    className={cn(
      "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-[var(--color-border)] px-8 py-12 text-center",
      className,
    )}
  >
    {Icon && (
      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--color-accent)] text-[var(--color-accent-foreground)]">
        <Icon className="h-5 w-5" />
      </div>
    )}
    <div className="flex flex-col gap-1">
      <p className="font-medium text-sm text-[var(--color-foreground)]">{title}</p>
      {description && (
        <p className="text-sm text-[var(--color-muted-foreground)] max-w-sm">{description}</p>
      )}
    </div>
    {action}
  </div>
);
