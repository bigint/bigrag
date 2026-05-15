import { cn } from "@/lib/cn";

type Props = {
  readonly children: React.ReactNode;
  readonly className?: string;
};

export const PageContainer = ({ children, className }: Props) => (
  <div className={cn("mx-auto w-full max-w-7xl", className)}>{children}</div>
);
