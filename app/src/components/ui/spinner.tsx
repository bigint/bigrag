import { cn } from "@/lib/cn";

type Props = { size?: "sm" | "md" | "lg"; className?: string };

export const Spinner = ({ size = "md", className }: Props) => (
  <span
    className={cn(
      "inline-block rounded-full border-2 border-current border-t-transparent",
      "animate-[spin-slow_600ms_linear_infinite]",
      size === "sm" && "h-3.5 w-3.5",
      size === "md" && "h-5 w-5",
      size === "lg" && "h-7 w-7",
      className,
    )}
    role="status"
    aria-label="Loading"
  />
);
