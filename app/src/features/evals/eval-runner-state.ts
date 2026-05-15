export type EvalCase = { query: string; relevant_ids: string[] };

export type EvalRunnerFormValues = {
  cases: string;
  collection: string;
  topK: number;
};

export const SAMPLE_EVAL_CASES = `[
  { "query": "how do I create a collection?", "relevant_ids": ["doc-abc"] },
  { "query": "what embedding models are supported?", "relevant_ids": ["doc-def"] }
]`;

export const defaultEvalRunnerFormValues = (): EvalRunnerFormValues => ({
  cases: SAMPLE_EVAL_CASES,
  collection: "",
  topK: 10,
});

export const parseEvalCases = (cases: string): EvalCase[] => {
  const parsed = JSON.parse(cases);
  if (!Array.isArray(parsed) || parsed.length === 0) {
    throw new Error("Expected a non-empty JSON array of cases");
  }
  return parsed as EvalCase[];
};

export const evalCasesError = (cases: string): string | undefined => {
  try {
    parseEvalCases(cases);
    return undefined;
  } catch (err) {
    return err instanceof Error ? `Invalid JSON: ${err.message}` : "Invalid JSON";
  }
};

export const validateEvalRunnerFormValues = ({
  cases,
  collection,
  topK,
}: EvalRunnerFormValues): string | undefined => {
  if (!collection) return "Collection is required";
  if (topK < 1 || topK > 100) return "top_k must be between 1 and 100";
  return evalCasesError(cases);
};

export const evalRunnerBodyFromValues = ({ cases, collection, topK }: EvalRunnerFormValues) => ({
  cases: parseEvalCases(cases),
  collection,
  search_mode: "semantic",
  top_k: topK,
});
