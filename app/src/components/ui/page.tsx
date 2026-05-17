import { cn } from "@/lib/cn";

type ContainerProps = {
  readonly children: React.ReactNode;
  readonly className?: string;
};

const Container = ({ children, className }: ContainerProps) => (
  <div className={cn("mx-auto w-full max-w-7xl", className)}>{children}</div>
);

type ShellProps = {
  readonly children: React.ReactNode;
  readonly className?: string;
};

const Shell = ({ children, className }: ShellProps) => (
  <div className={cn("flex w-full flex-col gap-6", className)}>{children}</div>
);

type HeaderProps = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
  className?: string;
};

const Header = ({ title, description, actions, eyebrow, className }: HeaderProps) => (
  <div className={cn(className)}>
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

export const Page = {
  Container,
  Shell,
  Header,
};
