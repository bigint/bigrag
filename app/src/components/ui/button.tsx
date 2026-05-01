"use client";

import { Button as BaseButton } from "@base-ui/react/button";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, Ref } from "react";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-full text-sm font-semibold transition-all duration-200 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 active:scale-95",
  {
    defaultVariants: {
      size: "md",
      variant: "primary",
    },
    variants: {
      size: {
        lg: "h-10 px-5",
        md: "h-9 px-4",
        sm: "h-8 px-3 text-xs",
        icon: "h-9 w-9",
      },
      variant: {
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        ghost: "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
        primary: "bg-primary text-primary-foreground hover:bg-neutral-800",
        secondary: "border border-border bg-muted text-foreground hover:bg-accent",
        outline: "border border-border bg-background text-foreground hover:bg-muted",
      },
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & { ref?: Ref<HTMLButtonElement> };

export const Button = ({
  className,
  variant,
  size,
  type = "button",
  ref,
  ...props
}: ButtonProps) => (
  <BaseButton
    className={cn(buttonVariants({ className, size, variant }))}
    ref={ref}
    type={type}
    {...props}
  />
);
