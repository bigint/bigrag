import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

interface QueryErrorProps {
  readonly error: unknown;
  readonly title?: string;
  readonly onRetry?: () => void;
  readonly className?: string;
}

export const QueryError = ({
  error,
  title = "Failed to load data",
  onRetry,
  className,
}: QueryErrorProps) => (
  <div className={cn("rounded-xl border border-destructive/30 bg-destructive/10 p-6", className)}>
    <h2 className="text-sm font-semibold text-destructive">{title}</h2>
    <p className="mt-1 text-sm text-destructive">
      {error instanceof Error ? error.message : "Unknown error"}
    </p>
    {onRetry && (
      <div className="mt-4">
        <Button onClick={onRetry} variant="secondary">
          Retry
        </Button>
      </div>
    )}
  </div>
);
