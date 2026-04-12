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
      <div className="flex w-full flex-col gap-1.5">
        {label && (
          <label htmlFor={selectId} className="text-xs font-medium">
            {label}
          </label>
        )}
        <select
          id={selectId}
          ref={ref}
          className={cn(
            "flex h-9 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "text-foreground",
            "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background",
            "transition-colors duration-150",
            "disabled:cursor-not-allowed disabled:opacity-50",
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
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
    );
  },
);
Select.displayName = "Select";
