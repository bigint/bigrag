import { describe, expect, it } from "vitest";
import {
  defaultEvalRunnerFormValues,
  evalCasesError,
  evalRunnerBodyFromValues,
  parseEvalCases,
  SAMPLE_EVAL_CASES,
  validateEvalRunnerFormValues,
} from "./eval-runner-state";

describe("eval runner state", () => {
  it("builds default eval values", () => {
    expect(defaultEvalRunnerFormValues()).toEqual({
      cases: SAMPLE_EVAL_CASES,
      collection: "",
      topK: 10,
    });
  });

  it("parses only non-empty JSON arrays", () => {
    expect(parseEvalCases('[{"query":"q","relevant_ids":["doc"]}]')).toEqual([
      { query: "q", relevant_ids: ["doc"] },
    ]);
    expect(() => parseEvalCases("[]")).toThrow("Expected a non-empty JSON array of cases");
    expect(evalCasesError("{")).toContain("Invalid JSON");
  });

  it("validates submitted eval values", () => {
    expect(validateEvalRunnerFormValues(defaultEvalRunnerFormValues())).toBe(
      "Collection is required",
    );
    expect(
      validateEvalRunnerFormValues({
        cases: SAMPLE_EVAL_CASES,
        collection: "docs",
        topK: 0,
      }),
    ).toBe("top_k must be between 1 and 100");
    expect(
      validateEvalRunnerFormValues({
        cases: "[]",
        collection: "docs",
        topK: 10,
      }),
    ).toBe("Invalid JSON: Expected a non-empty JSON array of cases");
  });

  it("builds the evaluation request body", () => {
    expect(
      evalRunnerBodyFromValues({
        cases: '[{"query":"q","relevant_ids":["doc"]}]',
        collection: "docs",
        topK: 3,
      }),
    ).toEqual({
      cases: [{ query: "q", relevant_ids: ["doc"] }],
      collection: "docs",
      search_mode: "semantic",
      top_k: 3,
    });
  });
});
