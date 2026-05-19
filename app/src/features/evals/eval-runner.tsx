import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Textarea,
} from "@atelier/ui";
import { useForm, useStore } from "@tanstack/react-form";
import { useMutation } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import {
  defaultEvalRunnerFormValues,
  type EvalCase,
  evalCasesError,
  evalRunnerBodyFromValues,
  SAMPLE_EVAL_CASES,
  validateEvalRunnerFormValues,
} from "@/features/evals/eval-runner-state";
import { useCollections } from "@/hooks/use-collections";
import { apiClient } from "@/lib/api";
import { errorText, firstString, submitWith } from "@/lib/form";

type EvalPerCase = {
  query: string;
  hit_ids: string[];
  expected_ids: string[];
  recall_at_k: number;
  reciprocal_rank: number;
  ndcg_at_k: number;
};

type EvalResponse = {
  collection: string;
  total_cases: number;
  recall_at_k_avg: number;
  mrr: number;
  ndcg_at_k_avg: number;
  per_case: EvalPerCase[];
};

export const EvalRunner = () => {
  const { data: collectionsData } = useCollections();
  const collections = collectionsData?.collections ?? [];

  const [result, setResult] = useState<EvalResponse | null>(null);

  const mutation = useMutation({
    mutationFn: (body: {
      collection: string;
      cases: EvalCase[];
      top_k: number;
      search_mode: string;
    }) => apiClient.post<EvalResponse>("v1/evaluation", body),
    onSuccess: (r) => {
      setResult(r);
      toast.success(`Evaluated ${r.total_cases} cases - recall@k ${r.recall_at_k_avg}`);
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Failed");
    },
  });
  const form = useForm({
    defaultValues: defaultEvalRunnerFormValues(),
    validators: {
      onSubmit: ({ value }) => validateEvalRunnerFormValues(value),
    },
    onSubmit: ({ value }) => {
      try {
        mutation.mutate(evalRunnerBodyFromValues(value));
      } catch (err) {
        toast.error(err instanceof Error ? `Invalid JSON: ${err.message}` : "Invalid JSON");
      }
    },
  });
  const values = useStore(form.store, (state) => state.values);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Batch run</CardTitle>
        <CardDescription>
          Upload a batch of <code className="text-xs">{"{query, relevant_ids}"}</code> cases and
          compare retrieved chunks against known relevant IDs.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="flex flex-col gap-4"
          noValidate
          onSubmit={submitWith(() => form.handleSubmit())}
        >
          <form.Subscribe selector={(state) => state.errors}>
            {(errors) => {
              const formError = firstString(errors);
              return formError ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {formError}
                </div>
              ) : null;
            }}
          </form.Subscribe>
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-foreground" htmlFor="eval-col">
              Collection
            </label>
            <form.Field
              name="collection"
              validators={{
                onSubmit: ({ value }) => (value ? undefined : "Collection is required"),
              }}
            >
              {(field) => (
                <>
                  <select
                    className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                    id="eval-col"
                    onBlur={field.handleBlur}
                    onChange={(e) => field.handleChange(e.target.value)}
                    required
                    value={field.state.value}
                  >
                    <option value="" disabled>
                      Pick a collection...
                    </option>
                    {collections.map((c) => (
                      <option key={c.name} value={c.name}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                  {errorText(field.state.meta.errors) && (
                    <p className="text-xs text-destructive">{errorText(field.state.meta.errors)}</p>
                  )}
                </>
              )}
            </form.Field>
          </div>

          <form.Field
            name="topK"
            validators={{
              onSubmit: ({ value }) =>
                value < 1 || value > 100 ? "top_k must be between 1 and 100" : undefined,
            }}
          >
            {(field) => (
              <Input
                error={errorText(field.state.meta.errors)}
                label="top_k"
                max={100}
                min={1}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                type="number"
                value={field.state.value}
              />
            )}
          </form.Field>

          <div className="flex flex-col gap-2">
            <label htmlFor="eval-cases" className="text-sm font-medium text-foreground">
              Cases (JSON)
            </label>
            <form.Field
              name="cases"
              validators={{
                onSubmit: ({ value }) => evalCasesError(value),
              }}
            >
              {(field) => (
                <Textarea
                  className="font-mono text-xs"
                  error={errorText(field.state.meta.errors)}
                  id="eval-cases"
                  onBlur={field.handleBlur}
                  onChange={(e) => field.handleChange(e.target.value)}
                  placeholder={SAMPLE_EVAL_CASES}
                  rows={8}
                  spellCheck={false}
                  value={field.state.value}
                />
              )}
            </form.Field>
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={mutation.isPending || !values.collection}>
              <Play className="size-4" />
              {mutation.isPending ? "Running..." : "Run eval"}
            </Button>
          </div>
        </form>

        {result && (
          <div className="mt-6 space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <StatCard label="Recall@k avg" value={result.recall_at_k_avg.toFixed(3)} />
              <StatCard label="MRR" value={result.mrr.toFixed(3)} />
              <StatCard label="nDCG@k avg" value={result.ndcg_at_k_avg.toFixed(3)} />
            </div>
            <div className="overflow-hidden rounded-md border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Query</th>
                    <th className="px-3 py-2 text-right font-medium">Recall</th>
                    <th className="px-3 py-2 text-right font-medium">RR</th>
                    <th className="px-3 py-2 text-right font-medium">nDCG</th>
                  </tr>
                </thead>
                <tbody>
                  {result.per_case.map((c) => (
                    <tr key={c.query} className="border-t border-border">
                      <td className="px-3 py-2 text-xs text-foreground">
                        <div className="line-clamp-2">{c.query}</div>
                      </td>
                      <td className="px-3 py-2 text-right text-xs">{c.recall_at_k}</td>
                      <td className="px-3 py-2 text-right text-xs">{c.reciprocal_rank}</td>
                      <td className="px-3 py-2 text-right text-xs">{c.ndcg_at_k}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const StatCard = ({ label, value }: { label: string; value: string }) => (
  <div className="rounded-md border border-border bg-card p-3">
    <div className="text-xs text-muted-foreground">{label}</div>
    <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
  </div>
);
