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
    {eyebrow && <div className="mb-1 text-xs font-semibold text-muted-foreground">{eyebrow}</div>}
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 flex-1">
        <h1 className="text-3xl leading-tight font-semibold tracking-normal">{title}</h1>
        {description && (
          <p className="mt-2 max-w-4xl text-pretty text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  </div>
);
