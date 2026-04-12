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
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-xs font-medium text-foreground">
            {label}
          </label>
        )}
        <div className="relative">
          <input
            id={inputId}
            ref={ref}
            aria-invalid={!!error}
            className={cn(
              "flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
              "text-foreground placeholder:text-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
              "transition-colors duration-150",
              "disabled:cursor-not-allowed disabled:opacity-50",
              error && "border-destructive",
              trailing && "pr-9",
              className,
            )}
            {...props}
          />
          {trailing && (
            <div className="absolute inset-y-0 right-0 flex items-center pr-2 text-muted-foreground">
              {trailing}
            </div>
          )}
        </div>
        {description && !error && <p className="text-xs text-muted-foreground">{description}</p>}
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
    );
  },
);
Input.displayName = "Input";
