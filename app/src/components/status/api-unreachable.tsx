import { Button } from "@atelier/ui";

type Props = {
  readonly error?: unknown;
  readonly onRetry?: () => void;
  readonly variant?: "page" | "card";
};

const defaultMessage = "The bigRAG API did not respond.";

const errorMessage = (error: unknown): string => {
  if (!error) return defaultMessage;
  if (error instanceof Error) return error.message;
  return defaultMessage;
};

export const ApiUnreachable = ({ error, onRetry, variant = "page" }: Props) => {
  const message = errorMessage(error);
  if (variant === "card") {
    return (
      <div className="w-full max-w-sm rounded-xl border border-destructive/40 bg-card p-6">
        <h1 className="font-semibold text-base">Can't reach bigRAG</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        {import.meta.env.DEV ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Make sure the bigRAG server is running and{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono">VITE_BIGRAG_URL</code> points
            to the API.
          </p>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">
            The bigRAG API is not reachable. Try again in a moment, or contact your administrator.
          </p>
        )}
        {onRetry && (
          <Button className="mt-4" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
    );
  }
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6">
        <h1 className="text-base font-semibold">API unreachable</h1>
        <p className="mt-2 text-sm text-muted-foreground">{message}</p>
        {onRetry && (
          <Button className="mt-4" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
    </div>
  );
};
