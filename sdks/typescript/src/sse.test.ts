import { describe, expect, it } from "vitest";
import { parseSSEStream } from "./sse.js";

const responseFrom = (chunks: string[]) =>
  new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(new TextEncoder().encode(chunk));
        }
        controller.close();
      },
    }),
  );

describe("parseSSEStream", () => {
  it("parses split events and ignores comments", async () => {
    const response = responseFrom([
      ": ping\n",
      'data: {"event":"progress","data":{"progress":0.5}}\n\n',
      'data: {"event":"done","data":',
      '{"status":"ok"}}\n\n',
    ]);

    const events = [];
    for await (const event of parseSSEStream(response)) {
      events.push(event);
    }

    expect(events).toEqual([
      { event: "progress", data: { progress: 0.5 } },
      { event: "done", data: { status: "ok" } },
    ]);
  });

  it("parses a final unterminated data frame", async () => {
    const response = responseFrom(['data: {"event":"done","data":{"status":"ok"}}']);

    const events = [];
    for await (const event of parseSSEStream(response)) {
      events.push(event);
    }

    expect(events).toEqual([{ event: "done", data: { status: "ok" } }]);
  });

  it("throws on malformed JSON", async () => {
    const response = responseFrom(["data: nope\n\n"]);
    const stream = parseSSEStream(response);

    await expect(stream.next()).rejects.toMatchObject({
      name: "SSEParseError",
      raw: "nope",
    });
  });
});
