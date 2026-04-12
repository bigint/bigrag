"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/cn";

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  description?: string;
  error?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, description, error, id, ...props }, ref) => {
    const textareaId = id ?? `textarea-${label?.replace(/\s+/g, "-").toLowerCase()}`;
    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label && (
          <label htmlFor={textareaId} className="text-xs font-medium">
            {label}
          </label>
        )}
        <textarea
          id={textareaId}
          ref={ref}
          aria-invalid={!!error}
          className={cn(
            "min-h-[80px] w-full rounded-md border bg-[var(--color-card)] px-3 py-2 text-sm",
            "border-[var(--color-input)] text-[var(--color-foreground)]",
            "placeholder:text-[var(--color-muted-foreground)]",
            "focus:outline-none focus:border-[var(--color-ring)] focus:shadow-[var(--shadow-glow)]",
            "transition-[box-shadow,border-color] duration-[var(--duration-fast)]",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "resize-y",
            error && "border-[var(--color-destructive)]",
            className,
          )}
          {...props}
        />
        {description && !error && (
          <p className="text-xs text-[var(--color-muted-foreground)]">{description}</p>
        )}
        {error && <p className="text-xs text-[var(--color-destructive)]">{error}</p>}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";
