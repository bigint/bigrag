import { cn } from "@/lib/cn";

export const Kbd = ({ children, className }: { children: React.ReactNode; className?: string }) => (
  <kbd
    className={cn(
      "inline-flex items-center justify-center rounded-md border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground",
      className,
    )}
  >
    {children}
  </kbd>
);
