import { describe, expect, it, vi } from "vitest";
import { BigRAG } from "./client.js";
import {
  APIConnectionError,
  APITimeoutError,
  AuthenticationError,
  NotFoundError,
  RateLimitError,
} from "./errors.js";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("BigRAGCore", () => {
  it("sends auth, user agent, query params, and parses JSON", async () => {
    const fetch = vi.fn(async () => jsonResponse({ status: "ok" }));
    const client = new BigRAG({
      apiKey: "bigrag_sk_test",
      baseUrl: "http://api.local/",
      fetch,
    });

    await expect(client.getUsage({ windowDays: 7 })).resolves.toEqual({ status: "ok" });

    expect(fetch).toHaveBeenCalledWith(
      "http://api.local/v1/usage?window_days=7",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer bigrag_sk_test",
          "User-Agent": "bigrag-typescript/2026.5.7",
        }),
      }),
    );
  });

  it("adds explicit idempotency keys to mutating JSON requests", async () => {
    const fetch = vi.fn(async () => jsonResponse({ id: "col" }, { status: 201 }));
    const client = new BigRAG({ baseUrl: "http://api.local", fetch });

    await client._request("POST", "/v1/collections", {
      json: { name: "docs" },
      idempotencyKey: "idem_123",
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://api.local/v1/collections",
      expect.objectContaining({
        body: JSON.stringify({ name: "docs" }),
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "Idempotency-Key": "idem_123",
        }),
        method: "POST",
      }),
    );
  });

  it("can disable automatic idempotency keys", async () => {
    const fetch = vi.fn(async () => jsonResponse({ id: "col" }, { status: 201 }));
    const client = new BigRAG({
      baseUrl: "http://api.local",
      fetch,
      autoIdempotencyKey: false,
    });

    await client._request("POST", "/v1/collections", { json: { name: "docs" } });

    const init = (fetch.mock.calls as unknown as Array<[string, RequestInit]>)[0][1];
    expect(init.headers).not.toHaveProperty("Idempotency-Key");
  });

  it("adds automatic idempotency keys to mutating requests", async () => {
    const fetch = vi.fn(async () => jsonResponse({ id: "col" }, { status: 201 }));
    const client = new BigRAG({ baseUrl: "http://api.local", fetch });

    await client._request("POST", "/v1/collections", { json: { name: "docs" } });

    const init = (fetch.mock.calls as unknown as Array<[string, RequestInit]>)[0][1];
    expect(init.headers).toHaveProperty("Idempotency-Key");
  });

  it("maps empty and no-content responses to ok status", async () => {
    const noContent = new BigRAG({
      baseUrl: "http://api.local",
      fetch: vi.fn(async () => new Response(null, { status: 204 })),
    });
    const empty = new BigRAG({
      baseUrl: "http://api.local",
      fetch: vi.fn(async () => new Response("", { status: 200 })),
    });

    await expect(noContent._request("DELETE", "/v1/collections/docs")).resolves.toEqual({
      status: "ok",
    });
    await expect(empty._request("GET", "/health")).resolves.toEqual({ status: "ok" });
  });

  it("submits multipart uploads with auth and idempotency", async () => {
    const fetch = vi.fn(async () => jsonResponse({ id: "doc" }, { status: 201 }));
    const client = new BigRAG({
      apiKey: "bigrag_sk_test",
      baseUrl: "http://api.local",
      fetch,
    });
    const form = new FormData();
    form.append("file", new Blob(["hello"]), "hello.txt");

    await client._requestFormData("/v1/collections/docs/documents", form, {
      idempotencyKey: "idem_upload",
    });

    const init = (fetch.mock.calls as unknown as Array<[string, RequestInit]>)[0][1];
    expect(init.body).toBe(form);
    expect(init.headers).toEqual(
      expect.objectContaining({
        Authorization: "Bearer bigrag_sk_test",
        "Idempotency-Key": "idem_upload",
      }),
    );
    expect(init.headers).not.toHaveProperty("Content-Type");
  });

  it("maps structured error bodies to typed errors", async () => {
    const cases: Array<[number, new (...args: never[]) => Error]> = [
      [401, AuthenticationError],
      [404, NotFoundError],
      [429, RateLimitError],
    ];

    for (const [status, errorClass] of cases) {
      const fetch = vi.fn(async () => jsonResponse({ detail: `status ${status}` }, { status }));
      const client = new BigRAG({ baseUrl: "http://api.local", fetch, maxRetries: 0 });

      await expect(client.health()).rejects.toBeInstanceOf(errorClass);
    }
  });

  it("maps timeout and connection failures", async () => {
    const timeout = new Error("deadline");
    timeout.name = "TimeoutError";
    const timeoutClient = new BigRAG({
      baseUrl: "http://api.local",
      fetch: vi.fn(async () => {
        throw timeout;
      }),
      maxRetries: 0,
    });

    await expect(timeoutClient.health()).rejects.toBeInstanceOf(APITimeoutError);

    const connectionClient = new BigRAG({
      baseUrl: "http://api.local",
      fetch: vi.fn(async () => {
        throw new TypeError("socket closed");
      }),
      maxRetries: 0,
    });

    await expect(connectionClient.health()).rejects.toBeInstanceOf(APIConnectionError);
  });

  it("retries transient server errors", async () => {
    vi.useFakeTimers();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "temporary" }, { status: 503 }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }));
    const client = new BigRAG({ baseUrl: "http://api.local", fetch, maxRetries: 1 });

    const result = client.health();
    await vi.advanceTimersByTimeAsync(1000);

    await expect(result).resolves.toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });
});
