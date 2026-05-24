import type { ReactNode } from "react";
import { Switch } from "@/components/ui/switch";

export const ToggleFieldCard = ({
  ariaLabel,
  checked,
  children,
  description,
  onCheckedChange,
  title,
}: {
  ariaLabel: string;
  checked: boolean;
  children?: ReactNode;
  description: string;
  onCheckedChange: (checked: boolean) => void;
  title: string;
}) => (
  <div className="rounded-md border border-border bg-background p-3">
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-sm font-semibold">{title}</div>
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch aria-label={ariaLabel} checked={checked} onCheckedChange={onCheckedChange} />
    </div>
    {checked && children}
  </div>
);
