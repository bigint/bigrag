import { cn } from "@/lib/cn";

type Props = { className?: string; size?: "sm" | "md" | "lg" };

export const Logo = ({ className, size = "md" }: Props) => {
  const box = size === "sm" ? "h-7 w-7" : size === "lg" ? "h-10 w-10" : "h-8 w-8";
  const text = size === "sm" ? "text-sm" : size === "lg" ? "text-xl" : "text-base";
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div
        className={cn(
          "relative flex items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 text-white shadow-[var(--shadow-sm)]",
          box,
        )}
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-3/5 w-3/5" aria-hidden>
          <title>bigRAG</title>
          <path
            d="M4 7v10a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M4 7l8-4 8 4-8 4-8-4z"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          <circle cx="12" cy="13" r="2" fill="currentColor" />
        </svg>
      </div>
      <div className="flex flex-col leading-none">
        <span
          className={cn(
            "font-semibold tracking-[-0.02em] text-[var(--color-foreground)]",
            text,
          )}
        >
          bigRAG
        </span>
        <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--color-muted-foreground)]">
          Studio
        </span>
      </div>
    </div>
  );
};
