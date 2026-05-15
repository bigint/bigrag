import { useForm, useStore } from "@tanstack/react-form";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Search, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import {
  collectionSearchBodyFromValues,
  type CollectionSearchMode,
  defaultCollectionSearchFormValues,
  validateCollectionSearchFormValues,
} from "@/features/collections/collection-form-state";
import { useCollection } from "@/hooks/use-collections";
import { useRunQuery } from "@/hooks/use-query";
import { errorText, submitWith } from "@/lib/form";

export const Route = createFileRoute("/_dashboard/collections/$name/search")({
  component: () => <SearchTab />,
});

const SearchTab = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);
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
      <Card>
        <CardContent className="pt-5">
          <form className="flex flex-col gap-4" noValidate onSubmit={submitWith(() => form.handleSubmit())}>
            <form.Field
              name="query"
              validators={{
                onSubmit: ({ value }) => (value.trim() ? undefined : "Query is required"),
              }}
            >
              {(field) => (
                <Input
                  autoFocus
                  error={errorText(field.state.meta.errors)}
                  onBlur={field.handleBlur}
                  onChange={(e) => field.handleChange(e.target.value)}
                  placeholder="Ask a question of this collection…"
                  trailing={<Search className="h-4 w-4" />}
                  value={field.state.value}
                />
              )}
            </form.Field>
            <div className="flex flex-wrap items-end gap-3">
              <form.Field name="mode">
                {(field) => (
                  <Select
                    className="w-40"
                    label="Mode"
                    onChange={(value) => field.handleChange(value as CollectionSearchMode)}
                    options={[
                      { value: "semantic", label: "Semantic" },
                      { value: "keyword", label: "Keyword" },
                      { value: "hybrid", label: "Hybrid" },
                    ]}
                    value={field.state.value}
                  />
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
              {collection?.reranking_enabled && (
                <div className="flex items-center gap-2 text-sm">
                  <form.Field name="rerank">
                    {(field) => (
                      <Switch
                        aria-label="Rerank results"
                        checked={field.state.value}
                        onCheckedChange={field.handleChange}
                      />
                    )}
                  </form.Field>
                  <span>Rerank</span>
                </div>
              )}
              <div className="ml-auto">
                <Button type="submit" disabled={run.isPending || !values.query.trim()}>
                  {run.isPending ? (
                    <Spinner size="sm" />
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" /> Run query
                    </>
                  )}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>
      </Card>

      {run.data && run.data.results.length === 0 && (
        <Empty
          icon={<Search className="size-6" />}
          title="No results"
          description="Try a different query, mode, or raise min score."
        />
      )}

      {run.data && run.data.results.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            {run.data.total} result{run.data.total === 1 ? "" : "s"} for "{run.data.query}"
          </div>
          {run.data.results.map((r) => (
            <article key={r.id} className="rounded-xl border border-border bg-card p-4">
              <div className="mb-2 flex items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <Badge variant="primary">score {r.score.toFixed(3)}</Badge>
                  {r.document_id && (
                    <Link
                      params={{ docId: r.document_id, name }}
                      to="/collections/$name/documents/$docId"
                      className="font-mono text-muted-foreground hover:text-primary"
                    >
                      {r.document_id.slice(0, 8)}#{r.chunk_index}
                    </Link>
                  )}
                </div>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{r.text}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
};
