"use client";

import { Switch as BaseSwitch } from "@base-ui/react/switch";
import { useId } from "react";
import { cn } from "@/lib/cn";

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
}

export const Switch = ({
  checked,
  onCheckedChange,
  label,
  disabled = false,
  className,
  "aria-label": ariaLabel,
}: SwitchProps) => {
  const labelId = useId();
  const Wrapper = label ? "label" : "div";
  return (
    <Wrapper className={cn("flex items-center gap-3", className)}>
      <BaseSwitch.Root
        aria-label={label ? undefined : ariaLabel}
        aria-labelledby={label ? labelId : undefined}
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
        className={cn(
          "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          checked ? "bg-primary" : "bg-input",
        )}
      >
        <BaseSwitch.Thumb
          className={cn(
            "pointer-events-none inline-block size-4 rounded-full bg-background shadow-sm ring-1 ring-border/10 transition-transform duration-150",
            checked ? "translate-x-4" : "translate-x-0",
          )}
        />
      </BaseSwitch.Root>
      {label && (
        <span className="text-sm" id={labelId}>
          {label}
        </span>
      )}
    </Wrapper>
  );
};
