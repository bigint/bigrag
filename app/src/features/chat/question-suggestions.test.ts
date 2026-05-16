import { describe, expect, it } from "vitest";
import {
  buildQuestionSuggestions,
  questionChunkOffset,
  readyQuestionDocuments,
} from "./question-suggestions";

const fixedRandom = () => 0;

describe("question suggestions", () => {
  it("samples ready documents with chunks", () => {
    const documents = [
      { chunk_count: 0, filename: "empty.pdf", id: "empty", status: "ready" },
      { chunk_count: 8, filename: "failed.pdf", id: "failed", status: "failed" },
      { chunk_count: 4, filename: "handbook.pdf", id: "handbook", status: "ready" },
    ];

    expect(readyQuestionDocuments(documents, 6, fixedRandom)).toEqual([documents[2]]);
  });

  it("chooses a chunk offset inside the available range", () => {
    expect(
      questionChunkOffset(
        { chunk_count: 50, filename: "handbook.pdf", id: "handbook", status: "ready" },
        24,
        () => 0.5,
      ),
    ).toBe(13);
  });

  it("builds five unique collection-specific questions from document text", () => {
    const questions = buildQuestionSuggestions({
      chunks: [
        {
          document_id: "handbook",
          metadata: {},
          text: "Vacation approval requires manager review. Expense policy requires receipts.",
        },
        {
          document_id: "security",
          metadata: {},
          text: "Security incidents require escalation and customer notification.",
        },
      ],
      collection: "team-handbook",
      documents: [
        { chunk_count: 3, filename: "Vacation Policy.pdf", id: "handbook", status: "ready" },
        { chunk_count: 2, filename: "Security Runbook.md", id: "security", status: "ready" },
      ],
      random: fixedRandom,
    });

    expect(questions).toHaveLength(5);
    expect(new Set(questions).size).toBe(5);
    expect(questions.join(" ")).toContain("vacation policy");
  });
});
