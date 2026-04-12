"use client";

import { Switch as BaseSwitch } from "@base-ui/react/switch";
import { cn } from "@/lib/cn";

type Props = {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
};

export const Switch = ({ checked, onCheckedChange, disabled, className, ...rest }: Props) => (
  <BaseSwitch.Root
    checked={checked}
    onCheckedChange={onCheckedChange}
    disabled={disabled}
    className={cn(
      "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors",
      "border-[var(--color-input)] bg-[var(--color-muted)]",
      "data-[checked]:bg-[var(--color-primary)] data-[checked]:border-[var(--color-primary)]",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] focus-visible:ring-offset-2",
      "disabled:opacity-50 disabled:cursor-not-allowed",
      className,
    )}
    {...rest}
  >
    <BaseSwitch.Thumb className="block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[checked]:translate-x-[18px]" />
  </BaseSwitch.Root>
);
