import { cn } from "@/lib/cn";

type Props = { className?: string; withWordmark?: boolean };

export const Logo = ({ className, withWordmark = true }: Props) => (
  <div className={cn("flex items-center gap-2", className)}>
    <svg
      aria-hidden="true"
      className="size-7 text-primary"
      fill="none"
      viewBox="0 0 32 32"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title>rag.computer</title>
      <rect fill="currentColor" height="32" rx="8" width="32" />
      <path d="M8 12L16 6L24 12V20L16 26L8 20V12Z" fill="white" opacity="0.9" />
      <path d="M16 6L24 12L16 18L8 12L16 6Z" fill="white" />
    </svg>
    {withWordmark && <span className="font-semibold tracking-tight">rag.computer</span>}
  </div>
);
