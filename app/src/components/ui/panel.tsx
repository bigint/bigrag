import { cn } from "@/lib/cn";

export const Panel = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => (
  <div className={cn("rounded-xl border border-border bg-background p-5", className)}>
    {children}
  </div>
);
