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
      "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border border-input bg-muted transition-colors",
      "data-[checked]:border-primary data-[checked]:bg-primary",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
      "disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...rest}
  >
    <BaseSwitch.Thumb className="block size-3.5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[checked]:translate-x-[18px]" />
  </BaseSwitch.Root>
);
