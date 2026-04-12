"use client";

import { Checkbox as BaseCheckbox } from "@base-ui/react/checkbox";
import { CheckIcon, MinusIcon } from "lucide-react";
import { useId } from "react";
import { cn } from "@/lib/cn";

interface CheckboxProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
  id?: string;
  indeterminate?: boolean;
  "aria-label"?: string;
}

export const Checkbox = ({
  checked,
  onCheckedChange,
  label,
  disabled = false,
  className,
  id,
  indeterminate = false,
  "aria-label": ariaLabel,
}: CheckboxProps) => {
  const generatedId = useId();
  const checkboxId = id ?? generatedId;
  return (
    <label className={cn("flex items-center gap-2", className)} htmlFor={checkboxId}>
      <BaseCheckbox.Root
        aria-label={ariaLabel}
        checked={checked}
        className={cn(
          "flex size-4 shrink-0 items-center justify-center rounded border border-input transition-colors duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          checked || indeterminate
            ? "border-primary bg-primary text-primary-foreground"
            : "bg-background",
        )}
        disabled={disabled}
        id={checkboxId}
        indeterminate={indeterminate}
        onCheckedChange={onCheckedChange}
      >
        <BaseCheckbox.Indicator className="flex items-center justify-center">
          {indeterminate ? (
            <MinusIcon aria-hidden="true" className="size-3" />
          ) : (
            <CheckIcon aria-hidden="true" className="size-3" />
          )}
        </BaseCheckbox.Indicator>
      </BaseCheckbox.Root>
      {label && <span className="text-sm">{label}</span>}
    </label>
  );
};
