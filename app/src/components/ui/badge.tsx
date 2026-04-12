import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badge = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium tabular-nums",
  {
    variants: {
      variant: {
        neutral:
          "bg-[var(--color-muted)] text-[var(--color-muted-foreground)] border-[var(--color-border)]",
        accent:
          "bg-[var(--color-accent)] text-[var(--color-accent-foreground)] border-transparent",
        success:
          "bg-[color-mix(in_oklab,var(--color-success),transparent_88%)] text-[var(--color-success)] border-transparent",
        warning:
          "bg-[color-mix(in_oklab,var(--color-warning),transparent_88%)] text-[var(--color-warning)] border-transparent",
        danger:
          "bg-[color-mix(in_oklab,var(--color-destructive),transparent_88%)] text-[var(--color-destructive)] border-transparent",
        info: "bg-[color-mix(in_oklab,var(--color-info),transparent_88%)] text-[var(--color-info)] border-transparent",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>;

export const Badge = ({ className, variant, ...props }: BadgeProps) => (
  <span className={cn(badge({ variant }), className)} {...props} />
);
