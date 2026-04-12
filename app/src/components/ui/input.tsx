"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/cn";

type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  description?: string;
  error?: string;
  trailing?: React.ReactNode;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, description, error, trailing, id, ...props }, ref) => {
    const inputId = id ?? `input-${label?.replace(/\s+/g, "-").toLowerCase()}`;
    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs font-medium text-[var(--color-foreground)]"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <input
            id={inputId}
            ref={ref}
            aria-invalid={!!error}
            className={cn(
              "flex h-10 w-full rounded-md border bg-[var(--color-card)] px-3 py-2 text-sm",
              "border-[var(--color-input)] text-[var(--color-foreground)]",
              "placeholder:text-[var(--color-muted-foreground)]",
              "focus:outline-none focus:border-[var(--color-ring)] focus:shadow-[var(--shadow-glow)]",
              "transition-[box-shadow,border-color] duration-[var(--duration-fast)]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              error && "border-[var(--color-destructive)]",
              trailing && "pr-10",
              className,
            )}
            {...props}
          />
          {trailing && (
            <div className="absolute inset-y-0 right-0 flex items-center pr-2 text-[var(--color-muted-foreground)]">
              {trailing}
            </div>
          )}
        </div>
        {description && !error && (
          <p className="text-xs text-[var(--color-muted-foreground)]">{description}</p>
        )}
        {error && <p className="text-xs text-[var(--color-destructive)]">{error}</p>}
      </div>
    );
  },
);
Input.displayName = "Input";
