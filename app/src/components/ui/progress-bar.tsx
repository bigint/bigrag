import { cn } from "@/lib/cn";

interface ProgressBarProps {
  readonly value: number;
  readonly className?: string;
  readonly fillClassName?: string;
}

export const ProgressBar = ({ value, className, fillClassName }: ProgressBarProps) => (
  <div className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)}>
    <div className={cn("h-full bg-primary", fillClassName)} style={{ width: `${value}%` }} />
  </div>
);
