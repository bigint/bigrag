"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/cn";

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  description?: string;
  options: { value: string; label: string }[];
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, description, options, id, ...props }, ref) => {
    const selectId = id ?? `select-${label?.replace(/\s+/g, "-").toLowerCase()}`;
    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label && (
          <label htmlFor={selectId} className="text-xs font-medium">
            {label}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          className={cn(
            "flex h-10 w-full rounded-md border bg-[var(--color-card)] px-3 py-2 text-sm",
            "border-[var(--color-input)] text-[var(--color-foreground)]",
            "focus:outline-none focus:border-[var(--color-ring)] focus:shadow-[var(--shadow-glow)]",
            "transition-[box-shadow,border-color] duration-[var(--duration-fast)]",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            className,
          )}
          {...props}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        {description && (
          <p className="text-xs text-[var(--color-muted-foreground)]">{description}</p>
        )}
      </div>
    );
  },
);
Select.displayName = "Select";
