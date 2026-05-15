import { describe, expect, it } from "vitest";
import {
  defaultEvalRunnerFormValues,
  evalCasesError,
  evalRunnerBodyFromValues,
  parseEvalCases,
  validateEvalRunnerFormValues,
} from "./eval-runner-state";

describe("eval runner state", () => {
  it("creates defaults and parses cases", () => {
    const defaults = defaultEvalRunnerFormValues();

    expect(defaults.collection).toBe("");
    expect(parseEvalCases(defaults.cases)).toHaveLength(2);
  });

  it("validates cases and builds payloads", () => {
    expect(evalCasesError("{}")).toBe("Invalid JSON: Expected a non-empty JSON array of cases");
    expect(validateEvalRunnerFormValues(defaultEvalRunnerFormValues())).toBe(
      "Collection is required",
    );
    expect(
      evalRunnerBodyFromValues({
        cases: `[{"query":"docs","relevant_ids":["doc_1"]}]`,
        collection: "docs",
        topK: 3,
      }),
    ).toEqual({
      cases: [{ query: "docs", relevant_ids: ["doc_1"] }],
      collection: "docs",
      search_mode: "semantic",
      top_k: 3,
    });
  });
});
