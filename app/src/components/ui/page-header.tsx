import { cn } from "@/lib/cn";

type Props = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
  className?: string;
};

export const PageHeader = ({ title, description, actions, eyebrow, className }: Props) => (
  <div
    className={cn(
      "flex flex-col gap-3 pb-5 md:flex-row md:items-end md:justify-between md:gap-6",
      className,
    )}
  >
    <div className="flex flex-col gap-1">
      {eyebrow && (
        <div className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted-foreground)]">
          {eyebrow}
        </div>
      )}
      <h1 className="text-2xl font-semibold tracking-[-0.02em] text-[var(--color-foreground)]">
        {title}
      </h1>
      {description && (
        <p className="text-sm text-[var(--color-muted-foreground)] max-w-2xl">{description}</p>
      )}
    </div>
    {actions && <div className="flex items-center gap-2">{actions}</div>}
  </div>
);
