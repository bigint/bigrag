import { useForm, useStore } from "@tanstack/react-form";
import { createFileRoute, Link } from "@tanstack/react-router";
import { CircleAlert, Copy, Database, Gauge, RotateCcw, Search, Sparkles, X } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
  collectionSearchBodyFromValues,
  defaultCollectionSearchFormValues,
  validateCollectionSearchFormValues,
} from "@/features/collections/collection-form-state";
import { SearchModeControl, SearchToggle } from "@/features/collections/collection-search-controls";
import { decodeCollectionName } from "@/features/collections/use-collection-name";
import { useCollection } from "@/hooks/use-collections";
import { useRunQuery } from "@/hooks/use-query";
import { errorText, submitWith } from "@/lib/form";
import type { QueryResult } from "@/types/bigrag";

export const Route = createFileRoute("/_dashboard/collections/$name/search")({
  component: () => <SearchTab />,
});

const SearchTab = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeCollectionName(rawName);
  const { data: collection } = useCollection(name);
  const run = useRunQuery(name);
  const form = useForm({
    defaultValues: defaultCollectionSearchFormValues(),
    validators: {
      onSubmit: ({ value }) => validateCollectionSearchFormValues(value),
    },
    onSubmit: async ({ value }) => {
      await run.mutateAsync(collectionSearchBodyFromValues(value));
    },
  });
  const values = useStore(form.store, (state) => state.values);

  return (
    <div className="flex flex-col gap-4">
      <Card className="overflow-hidden">
        <CardContent className="p-0">
          <form
            className="flex flex-col"
            noValidate
            onSubmit={submitWith(() => form.handleSubmit())}
          >
            <div className="flex flex-col gap-3 p-4 sm:p-5">
              <div className="flex items-center justify-between gap-3">
                <label className="text-sm font-semibold" htmlFor="collection-search-query">
                  Search query
                </label>
                <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                  {values.query.length}/500
                </span>
              </div>
              <form.Field
                name="query"
                validators={{
                  onSubmit: ({ value }) => {
                    if (!value.trim()) return "Query is required";
                    if (value.length > 500) return "Query must be 500 characters or fewer";
                    return undefined;
                  },
                }}
              >
                {(field) => (
                  <Input
                    autoFocus
                    className="h-12 text-base"
                    error={errorText(field.state.meta.errors)}
                    id="collection-search-query"
                    maxLength={500}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    placeholder="Ask a question of this collection"
                    trailing={<Search className="size-4" />}
                    value={field.state.value}
                  />
                )}
              </form.Field>
            </div>
            <div className="flex flex-col gap-3 border-t border-border bg-muted/35 p-4 sm:flex-row sm:items-end sm:p-5">
              <form.Field name="mode">
                {(field) => (
                  <SearchModeControl onChange={field.handleChange} value={field.state.value} />
                )}
              </form.Field>
              <form.Field
                name="topK"
                validators={{
                  onSubmit: ({ value }) =>
                    value < 1 || value > 50 ? "Top K must be between 1 and 50" : undefined,
                }}
              >
                {(field) => (
                  <Input
                    className="w-24"
                    error={errorText(field.state.meta.errors)}
                    label="Top K"
                    max={50}
                    min={1}
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(Number(e.target.value))}
                    type="number"
                    value={field.state.value}
                  />
                )}
              </form.Field>
              <div className="grid gap-3 sm:min-w-72 sm:grid-cols-2">
                <form.Field name="skipCache">
                  {(field) => (
                    <SearchToggle
                      checked={field.state.value}
                      label="Skip cache"
                      onCheckedChange={field.handleChange}
                    />
                  )}
                </form.Field>
                {collection?.reranking_enabled ? (
                  <form.Field name="rerank">
                    {(field) => (
                      <SearchToggle
                        checked={field.state.value}
                        label="Rerank"
                        onCheckedChange={field.handleChange}
                      />
                    )}
                  </form.Field>
                ) : (
                  <div className="hidden sm:block" />
                )}
              </div>
              <Button
                className="h-10 w-full sm:ml-auto sm:w-auto"
                type="submit"
                disabled={run.isPending || !values.query.trim()}
              >
                {run.isPending ? (
                  <Spinner size="sm" />
                ) : (
                  <>
                    <Sparkles className="size-4" /> Run query
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {run.isPending && (
        <Card className="rounded-xl">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <Spinner size="sm" />
              Searching {name}
            </div>
            <Button size="sm" variant="secondary" onClick={run.cancel}>
              <X className="size-4" />
              Cancel
            </Button>
          </CardContent>
        </Card>
      )}

      {run.isError && (
        <Card className="rounded-xl border-destructive/25">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="flex min-w-0 items-center gap-3">
              <CircleAlert className="size-4 text-destructive" />
              <div className="min-w-0">
                <h3 className="text-sm font-semibold">Search failed</h3>
                <p className="truncate text-sm text-muted-foreground">
                  {run.error instanceof Error ? run.error.message : "Query request failed."}
                </p>
              </div>
            </div>
            {run.variables && (
              <Button size="sm" variant="secondary" onClick={() => run.mutate(run.variables)}>
                <RotateCcw className="size-4" />
                Retry
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {run.data && run.data.results.length === 0 && (
        <Empty
          icon={<Search className="size-6" />}
          title="No results"
          description="Try a different query, mode, or raise min score."
        />
      )}

      {run.data && run.data.results.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
            <Badge variant="neutral">
              {run.data.total} result{run.data.total === 1 ? "" : "s"}
            </Badge>
            <span>for "{run.data.query}"</span>
            {run.data.timings?.total_ms === undefined
              ? ""
              : ` ${Math.round(run.data.timings.total_ms)}ms`}
            {run.data.timings && (
              <Badge variant={run.data.timings.cache_hit ? "warning" : "neutral"}>
                {run.data.timings.cache_hit ? (
                  <Database className="size-3" />
                ) : (
                  <Gauge className="size-3" />
                )}
                {run.data.timings.cache_hit ? "cache hit" : "live"}
              </Badge>
            )}
          </div>
          {run.data.results.map((r) => (
            <article key={r.id} className="rounded-xl border border-border bg-card p-4">
              <div className="mb-2 flex items-start justify-between gap-2 text-xs">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <Badge variant="primary">score {r.score.toFixed(3)}</Badge>
                  {r.document_id && (
                    <Link
                      params={{ docId: r.document_id, name }}
                      hash={r.chunk_index === null ? undefined : `chunk-${r.chunk_index}`}
                      to="/collections/$name/documents/$docId"
                      className="font-mono text-muted-foreground hover:text-primary"
                    >
                      {r.document_filename ?? r.document_id.slice(0, 8)}
                      {r.chunk_index === null ? "" : ` #${r.chunk_index}`}
                    </Link>
                  )}
                  <span className="text-muted-foreground">{resultMetadata(r)}</span>
                </div>
                <Button
                  aria-label="Copy result text"
                  size="icon"
                  variant="ghost"
                  onClick={() => {
                    navigator.clipboard.writeText(r.text);
                    toast.success("Result copied");
                  }}
                >
                  <Copy className="size-4" />
                </Button>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{r.text}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};

const resultMetadata = (result: QueryResult) => {
  const parts = [];
  if (result.page_no !== undefined && result.page_no !== null) parts.push(`page ${result.page_no}`);
  if (result.char_start !== undefined && result.char_start !== null) {
    parts.push(`chars ${result.char_start}-${result.char_end ?? "?"}`);
  }
  const metadataKeys = Object.keys(result.metadata ?? {}).filter(
    (key) =>
      !["page_no", "char_start", "char_end", "document_filename"].includes(key) &&
      typeof result.metadata[key] !== "object",
  );
  if (metadataKeys.length) parts.push(metadataKeys.slice(0, 3).join(", "));
  return parts.join(" · ");
};
