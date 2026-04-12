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
      <div className="flex w-full flex-col gap-1.5">
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
            "min-h-20 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm",
            "text-foreground placeholder:text-muted-foreground",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
            "transition-colors duration-150",
            "disabled:cursor-not-allowed disabled:opacity-50",
            error && "border-destructive",
            className,
          )}
          {...props}
        />
        {description && !error && <p className="text-xs text-muted-foreground">{description}</p>}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    );
  },
);
Textarea.displayName = "Textarea";
