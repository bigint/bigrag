import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useReadiness } from "@/hooks/use-platform";
import { cn } from "@/lib/cn";

const StatusRow = ({
  label,
  ok,
  hint,
}: {
  label: string;
  ok: boolean | undefined;
  hint?: string | null;
}) => (
  <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
    <div>
      <div className="font-medium text-foreground">{label}</div>
      {hint && <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div>}
    </div>
    <span
      className={cn(
        "shrink-0 text-sm font-medium",
        ok === undefined ? "text-muted-foreground" : ok ? "text-success" : "text-destructive",
      )}
    >
      {ok === undefined ? "—" : ok ? "operational" : "down"}
    </span>
  </div>
);

export const ServerTab = () => {
  const { data: readiness, error } = useReadiness();
  const status = readiness?.status ?? "unknown";

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>System health</CardTitle>
          <CardDescription>
            {readiness
              ? `Running bigRAG v${readiness.version} — status: ${status}`
              : error
                ? "Could not reach the API."
                : "Checking readiness…"}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <StatusRow label="Postgres" ok={readiness?.postgres} />
          <StatusRow
            label={
              readiness?.vector_store_provider
                ? `Vector store (${readiness.vector_store_provider})`
                : "Vector store"
            }
            ok={readiness?.vector_store}
          />
          <StatusRow label="Redis" ok={readiness?.redis} />
          <StatusRow
            label="Embeddings"
            ok={readiness?.embedding}
            hint={
              readiness?.embedding_error ??
              (readiness?.embedding_source === "preset"
                ? "via embedding preset"
                : readiness?.embedding_source === "collection"
                  ? "via collection-level key"
                  : undefined)
            }
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bootstrap wiring</CardTitle>
          <CardDescription>
            These coordinates must exist before the API can read database-backed settings.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
          <EnvRow label="Postgres" value="BIGRAG_DATABASE_URL" />
          <EnvRow label="Redis" value="BIGRAG_REDIS_URL" />
          <EnvRow label="Vector store" value="Admin Settings / Vector store" />
          <EnvRow label="Encryption" value="BIGRAG_MASTER_KEY" />
          <EnvRow label="Bind address" value="BIGRAG_HOST / BIGRAG_PORT" />
          <EnvRow label="Split admin UI" value="admin UI backend URL" />
        </CardContent>
      </Card>
    </div>
  );
};

const EnvRow = ({ label, value }: { label: string; value: string }) => (
  <div className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2">
    <code className="font-mono text-xs text-foreground">{label}</code>
    <span className="truncate text-xs text-muted-foreground">{value}</span>
  </div>
);
