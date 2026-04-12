import { cn } from "@/lib/cn";

type Props = React.HTMLAttributes<HTMLDivElement>;

export const Card = ({ className, ...props }: Props) => (
  <div
    className={cn(
      "rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-[var(--shadow-xs)]",
      className,
    )}
    {...props}
  />
);

export const CardHeader = ({ className, ...props }: Props) => (
  <div className={cn("flex flex-col gap-1 p-5", className)} {...props} />
);

export const CardTitle = ({ className, ...props }: Props) => (
  <h3 className={cn("font-semibold text-base leading-tight tracking-tight", className)} {...props} />
);

export const CardDescription = ({ className, ...props }: Props) => (
  <p className={cn("text-sm text-[var(--color-muted-foreground)]", className)} {...props} />
);

export const CardContent = ({ className, ...props }: Props) => (
  <div className={cn("px-5 pb-5", className)} {...props} />
);

export const CardFooter = ({ className, ...props }: Props) => (
  <div
    className={cn(
      "flex items-center gap-2 px-5 py-3 border-t border-[var(--color-border)]",
      className,
    )}
    {...props}
  />
);
