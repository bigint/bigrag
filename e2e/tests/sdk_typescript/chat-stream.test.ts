import { afterAll, beforeAll, describe, expect, it } from "vitest";
import type { BigRAG, ChatCreateBody, ChatStreamEvent, Collection } from "@bigrag/client";
import {
  cleanupApiKeys,
  cleanupCollections,
  createCollection,
  getAdminClient,
  uploadFixture,
} from "./helpers.js";

let client: BigRAG;
let coll: Collection;

beforeAll(async () => {
  ({ client } = await getAdminClient());
  coll = await createCollection(client);
  await uploadFixture(client, coll.name, "sample.txt");
  await uploadFixture(client, coll.name, "sample.md");
});

afterAll(async () => {
  await cleanupCollections();
  await cleanupApiKeys();
});

function chatBody(extra: Partial<ChatCreateBody>): ChatCreateBody {
  const body: ChatCreateBody = {
    message: extra.message ?? "what does the sample text say?",
    collection: extra.collection ?? coll.name,
    ...extra,
  };
  // Allow injecting an OpenAI-compatible key when the instance settings don't
  // have a default Chat API key (true for ad-hoc dev runs; the e2e env wires
  // BIGRAG_CHAT_API_KEY at deploy time, in which case this env var is unset).
  const providerKey = process.env.BIGRAG_E2E_CHAT_PROVIDER_API_KEY;
  const providerBaseUrl = process.env.BIGRAG_E2E_CHAT_PROVIDER_BASE_URL;
  if (providerKey && body.provider_api_key === undefined) {
    body.provider_api_key = providerKey;
  }
  if (providerBaseUrl && body.provider_base_url === undefined) {
    body.provider_base_url = providerBaseUrl;
  }
  return body;
}

describe("ChatResource", () => {
  it("create (non-streaming) returns an assistant message with sources", async () => {
    const resp = await client.chat.create(
      chatBody({ message: "what does the sample text say?" }),
    );
    expect(resp.assistant_message.role).toBe("assistant");
    expect(resp.assistant_message.status).toBe("complete");
    expect(typeof resp.assistant_message.content).toBe("string");
    expect(resp.assistant_message.content.length).toBeGreaterThan(0);
    expect(Array.isArray(resp.sources)).toBe(true);
    expect(typeof resp.message.id).toBe("string");
    expect(resp.message.role).toBe("user");
  });

  it("create accepts top_k and search_mode without erroring", async () => {
    const resp = await client.chat.create(
      chatBody({
        message: "summarise the documents",
        top_k: 3,
        search_mode: "semantic",
        temperature: 0.1,
      }),
    );
    expect(resp.assistant_message.status).toBe("complete");
  });

  it("stream yields delta events, an assistant_message, and a done sentinel", async () => {
    const events: ChatStreamEvent[] = [];
    let accumulated = "";
    for await (const ev of client.chat.stream(chatBody({ message: "stream please" }))) {
      events.push(ev);
      if (ev.event === "delta") accumulated += ev.data.delta;
      if (ev.event === "done") break;
    }
    const types = events.map((e) => e.event);
    expect(types).toContain("delta");
    expect(types).toContain("assistant_message");
    expect(types.at(-1)).toBe("done");
    expect(accumulated.length).toBeGreaterThan(0);

    const assistant = events.find(
      (e): e is Extract<ChatStreamEvent, { event: "assistant_message" }> =>
        e.event === "assistant_message",
    );
    expect(assistant).toBeDefined();
    expect(assistant?.data.role).toBe("assistant");
    expect(Array.isArray(assistant?.data.sources)).toBe(true);
  });

  it("stream surfaces a sources event referencing the seeded collection", async () => {
    let sourcesEvent: Extract<ChatStreamEvent, { event: "sources" }> | undefined;
    for await (const ev of client.chat.stream(chatBody({ message: "tell me about samples" }))) {
      if (ev.event === "sources") {
        sourcesEvent = ev;
      }
      if (ev.event === "done") break;
    }
    expect(sourcesEvent).toBeDefined();
    if (sourcesEvent) {
      expect(Array.isArray(sourcesEvent.data.sources)).toBe(true);
    }
  });

  it("stream begins with a user_message event echoing the request", async () => {
    const iter = client.chat.stream(chatBody({ message: "echo my message" }));
    let first: ChatStreamEvent | undefined;
    let consumed = 0;
    for await (const ev of iter) {
      first ??= ev;
      consumed += 1;
      if (ev.event === "done") break;
    }
    expect(first?.event).toBe("user_message");
    expect(consumed).toBeGreaterThan(1);
  });
});
