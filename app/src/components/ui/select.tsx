"use client";

import { Select as BaseSelect } from "@base-ui/react/select";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface SelectOption {
  value: string;
  label: string;
  icon?: ReactNode;
}

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: readonly SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
  label?: string;
  error?: string | null;
}

const TRIGGER_CLASS =
  "flex h-10 w-full items-center justify-between gap-2 rounded-full border border-input bg-background px-4 text-left text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50";

const ChevronIcon = () => (
  <svg
    aria-hidden="true"
    className="size-4 shrink-0 text-muted-foreground"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    viewBox="0 0 24 24"
  >
    <title>Toggle</title>
    <path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

const CheckIcon = () => (
  <svg
    aria-hidden="true"
    className="size-3.5"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    viewBox="0 0 24 24"
  >
    <title>Selected</title>
    <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export const Select = ({
  value,
  onChange,
  options,
  placeholder = "Select…",
  disabled = false,
  id,
  className,
  label,
  error,
}: SelectProps) => (
  <div className={cn("flex flex-col gap-1", className)}>
    {label && (
      <label className="text-sm font-semibold" id={id ? `${id}-label` : undefined} htmlFor={id}>
        {label}
      </label>
    )}
    <BaseSelect.Root
      disabled={disabled}
      onValueChange={(val) => onChange(val as string)}
      value={value}
    >
      <BaseSelect.Trigger
        className={cn(TRIGGER_CLASS, error && "border-destructive focus-visible:ring-destructive")}
        id={id}
      >
        <BaseSelect.Value placeholder={placeholder}>
          {(val: string) => {
            const match = options.find((o) => o.value === val);
            return match ? (
              <span className="flex min-w-0 items-center gap-2">
                {match.icon}
                <span className="truncate">{match.label}</span>
              </span>
            ) : (
              <span className="truncate">{val || placeholder}</span>
            );
          }}
        </BaseSelect.Value>
        <BaseSelect.Icon>
          <ChevronIcon />
        </BaseSelect.Icon>
      </BaseSelect.Trigger>
      <BaseSelect.Portal>
        <BaseSelect.Positioner alignItemWithTrigger={false} className="z-50" sideOffset={4}>
          <BaseSelect.Popup
            className="max-h-60 overflow-y-auto rounded-3xl border border-border bg-popover p-1.5"
            style={{ width: "var(--anchor-width)" }}
          >
            <BaseSelect.List>
              {options.map((option) => (
                <BaseSelect.Item
                  className="flex w-full cursor-default select-none items-center gap-2 rounded-xl px-3 py-2 text-sm outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
                  key={option.value}
                  value={option.value}
                >
                  <BaseSelect.ItemIndicator className="inline-flex size-4 shrink-0 items-center justify-center">
                    <CheckIcon />
                  </BaseSelect.ItemIndicator>
                  {option.icon}
                  <BaseSelect.ItemText>{option.label}</BaseSelect.ItemText>
                </BaseSelect.Item>
              ))}
            </BaseSelect.List>
          </BaseSelect.Popup>
        </BaseSelect.Positioner>
      </BaseSelect.Portal>
    </BaseSelect.Root>
    {error && <p className="text-xs text-destructive">{error}</p>}
  </div>
);
