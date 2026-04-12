import { cn } from "@/lib/cn";

type Props = { size?: "sm" | "md" | "lg"; className?: string };

export const Spinner = ({ size = "md", className }: Props) => (
  <span
    className={cn(
      "inline-block animate-[spin-slow_600ms_linear_infinite] rounded-full border-2 border-muted-foreground border-t-transparent",
      size === "sm" && "size-3.5 border",
      size === "md" && "size-5",
      size === "lg" && "size-7",
      className,
    )}
    role="status"
    aria-label="Loading"
  />
);
