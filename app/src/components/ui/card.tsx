import { cn } from "@/lib/cn";

type Props = React.HTMLAttributes<HTMLDivElement>;

export const Card = ({ className, ...props }: Props) => (
  <div className={cn("rounded-xl border border-border bg-card", className)} {...props} />
);

export const CardHeader = ({ className, ...props }: Props) => (
  <div className={cn("flex flex-col gap-1.5 p-5", className)} {...props} />
);

export const CardTitle = ({ className, ...props }: Props) => (
  <h3
    className={cn("font-semibold text-base leading-tight tracking-normal", className)}
    {...props}
  />
);

export const CardDescription = ({ className, ...props }: Props) => (
  <p className={cn("text-sm text-muted-foreground", className)} {...props} />
);

export const CardContent = ({ className, ...props }: Props) => (
  <div className={cn("px-5 pb-5", className)} {...props} />
);
