import { cn } from "@/lib/cn";

type Props = {
  readonly children: React.ReactNode;
  readonly className?: string;
};

export const PageShell = ({ children, className }: Props) => (
  <div className={cn("flex w-full flex-col gap-6", className)}>{children}</div>
);
