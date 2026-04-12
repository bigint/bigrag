import { cn } from "@/lib/cn";

type Props = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
  className?: string;
};

export const PageHeader = ({ title, description, actions, eyebrow, className }: Props) => (
  <div className={cn("mb-8", className)}>
    {eyebrow && (
      <div className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {eyebrow}
      </div>
    )}
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  </div>
);
