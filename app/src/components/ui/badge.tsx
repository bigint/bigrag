import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
  {
    defaultVariants: { dot: false, variant: "neutral" },
    variants: {
      dot: { false: "", true: "" },
      variant: {
        error: "bg-destructive/10 text-destructive",
        info: "bg-info/10 text-info",
        neutral: "bg-muted text-muted-foreground",
        primary: "bg-primary/10 text-primary",
        success: "bg-success/10 text-success",
        warning: "bg-warning/10 text-warning",
      },
    },
  },
);

const dotColorMap: Record<string, string> = {
  error: "bg-destructive",
  info: "bg-info",
  neutral: "bg-muted-foreground",
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
};

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

export const Badge = ({ className, variant, dot, children, ...props }: BadgeProps) => (
  <span className={cn(badgeVariants({ className, dot, variant }))} {...props}>
    {dot && <span className={cn("size-1.5 rounded-full", dotColorMap[variant ?? "neutral"])} />}
    {children}
  </span>
);
