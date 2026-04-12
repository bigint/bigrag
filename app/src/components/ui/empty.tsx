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
      "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-8 py-12 text-center",
      className,
    )}
  >
    {Icon && (
      <div className="flex size-11 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Icon className="size-5" />
      </div>
    )}
    <div className="flex flex-col gap-1">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
    </div>
    {action}
  </div>
);
