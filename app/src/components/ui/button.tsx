"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2 whitespace-nowrap",
    "font-medium text-sm tracking-[-0.01em]",
    "rounded-md border border-transparent",
    "transition-all duration-[var(--duration-fast)] ease-[var(--ease-out)]",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-background)]",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    "active:translate-y-px",
    "[&_svg]:size-4 [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary:
          "bg-[var(--color-primary)] text-[var(--color-primary-foreground)] shadow-[var(--shadow-sm)] hover:bg-[var(--color-primary-hover)]",
        secondary:
          "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-accent)] hover:text-[var(--color-accent-foreground)]",
        ghost:
          "bg-transparent text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-accent-foreground)]",
        destructive:
          "bg-[var(--color-destructive)] text-[var(--color-destructive-foreground)] shadow-[var(--shadow-sm)] hover:opacity-90",
        outline:
          "border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-accent-foreground)]",
      },
      size: {
        sm: "h-8 px-3 text-xs rounded-md",
        md: "h-9 px-4 rounded-md",
        lg: "h-11 px-6 text-base rounded-lg",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";

export { buttonVariants };
