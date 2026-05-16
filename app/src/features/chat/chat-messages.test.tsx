import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { type ChatMessage, ChatMessages } from "./chat-messages";

const messages: ChatMessage[] = [
  {
    id: "user-1",
    role: "user",
    content: "What was the total ITC?",
  },
  {
    id: "assistant-1",
    role: "assistant",
    content: "The total ITC was 12,283.82 [1].",
    meta: {
      collection: "arxiv",
      timings: {
        cache_hit: false,
        cache_ms: 0,
        embed_ms: 120,
        rerank_ms: 0,
        search_ms: 1100,
        total_ms: 1220,
      },
      sources: [
        {
          id: "source-1",
          chunk_index: 5,
          document_filename: "GSTR3B_032026.pdf",
          document_id: "doc-1",
          metadata: {},
          page_no: 5,
          score: 0.671,
          text: "Total ITC available 12,283.82",
        },
      ],
    },
  },
];

describe("ChatMessages", () => {
  it("keeps source evidence inside the answer instead of a persistent side ledger", () => {
    const html = renderToStaticMarkup(<ChatMessages isStreaming={false} messages={messages} />);

    expect(html).toContain("Sources");
    expect(html).toContain("1 / 1220ms");
    expect(html).toContain("GSTR3B_032026.pdf");
    expect(html).not.toContain("Evidence ledger");
  });
});
