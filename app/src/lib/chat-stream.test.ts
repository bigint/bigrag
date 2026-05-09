import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "./chat-stream";

const streamResponse = (frames: string[], init: ResponseInit = {}) =>
  new Response(
    new ReadableStream({
      start(controller) {
        for (const frame of frames) {
          controller.enqueue(new TextEncoder().encode(frame));
        }
        controller.close();
      },
    }),
    {
      status: 200,
      ...init,
    },
  );

describe("streamChat", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts a streaming chat body and emits parsed events", async () => {
    const fetch = vi.fn(async () =>
      streamResponse([
        'event: delta\ndata: {"delta":"hel"}\n\n',
        'event: delta\ndata: {"delta":"lo"}\n\n',
        "data: [DONE]\n\n",
      ]),
    );
    vi.stubGlobal("fetch", fetch);
    const events: unknown[] = [];

    await streamChat({
      body: { message: "Hi" },
      onEvent: (event) => events.push(event),
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:4000/v1/chat",
      expect.objectContaining({
        body: JSON.stringify({ message: "Hi", stream: true }),
        credentials: "include",
        method: "POST",
      }),
    );
    expect(events).toEqual([
      { event: "delta", data: { delta: "hel" } },
      { event: "delta", data: { delta: "lo" } },
    ]);
  });

  it("uses API error details when stream creation fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "Nope" }), { status: 400 })),
    );

    await expect(
      streamChat({
        body: { message: "Hi" },
        onEvent: () => {},
      }),
    ).rejects.toMatchObject({ message: "Nope", status: 400 });
  });
});
