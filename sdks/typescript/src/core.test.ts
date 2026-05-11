import { describe, expect, it, vi } from "vitest";
import { RagComputer } from "./client.js";
import {
  APIConnectionError,
  APIError,
  APITimeoutError,
  AuthenticationError,
  BadRequestError,
  InternalServerError,
  NotFoundError,
  RateLimitError,
} from "./errors.js";

const jsonResponse = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });

describe("RagComputerCore", () => {
  it("sends auth, user agent, query params, and parses JSON", async () => {
    const fetch = vi.fn(async () => jsonResponse({ status: "ok" }));
    const client = new RagComputer({
      apiKey: "ragc_sk_test",
      baseUrl: "http://api.local/",
      fetch,
    });

    await expect(client.getUsage({ windowDays: 7 })).resolves.toEqual({ status: "ok" });

    expect(fetch).toHaveBeenCalledWith(
      "http://api.local/v1/usage?window_days=7",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer ragc_sk_test",
          "User-Agent": "rag-computer-typescript/2026.5.7",
        }),
      }),
    );
  });

  it("builds platform endpoint requests", async () => {
    const fetch = vi.fn(async () => jsonResponse({ status: "ok" }));
    const client = new RagComputer({ baseUrl: "http://api.local", fetch });

    await client.health();
    await client.readiness();
    await client.getStats();
    await client.listEmbeddingModels();

    expect(fetch.mock.calls.map(([url, init]) => [url, init.method])).toEqual([
      ["http://api.local/health", "GET"],
      ["http://api.local/health/ready", "GET"],
      ["http://api.local/v1/stats", "GET"],
      ["http://api.local/v1/embeddings/models", "GET"],
    ]);
  });

  it("uses environment API keys and default error messages", async () => {
    const previous = process.env.RAG_COMPUTER_API_KEY;
    process.env.RAG_COMPUTER_API_KEY = "ragc_sk_env";
    const fetch = vi.fn(async () => jsonResponse({ status: "ok" }));

    try {
      const client = new RagComputer({ baseUrl: "http://api.local", fetch });
      await client.health();

      expect(fetch).toHaveBeenCalledWith(
        "http://api.local/health",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: "Bearer ragc_sk_env" }),
        }),
      );
    } finally {
      if (previous === undefined) delete process.env.RAG_COMPUTER_API_KEY;
      else process.env.RAG_COMPUTER_API_KEY = previous;
    }

    expect(new APIConnectionError().message).toBe("Connection error");
    expect(new APITimeoutError().message).toBe("Request timed out");
  });

  it("adds explicit idempotency keys to mutating JSON requests", async () => {
    const fetch = vi.fn(async () => jsonResponse({ id: "col" }, { status: 201 }));
    const client = new RagComputer({ baseUrl: "http://api.local", fetch });

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
    const client = new RagComputer({
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
    const client = new RagComputer({ baseUrl: "http://api.local", fetch });

    await client._request("POST", "/v1/collections", { json: { name: "docs" } });

    const init = (fetch.mock.calls as unknown as Array<[string, RequestInit]>)[0][1];
    expect(init.headers).toHaveProperty("Idempotency-Key");
  });

  it("falls back to Math.random for idempotency keys without Web Crypto", async () => {
    vi.stubGlobal("crypto", undefined);
    const random = vi.spyOn(Math, "random").mockReturnValue(0);
    const fetch = vi.fn(async () => jsonResponse({ id: "col" }, { status: 201 }));
    const client = new RagComputer({ baseUrl: "http://api.local", fetch });

    try {
      await client._request("POST", "/v1/collections", { json: { name: "docs" } });
    } finally {
      random.mockRestore();
      vi.unstubAllGlobals();
    }

    const init = (fetch.mock.calls as unknown as Array<[string, RequestInit]>)[0][1];
    expect(init.headers).toHaveProperty("Idempotency-Key", "00000000-0000-0000-0000-000000000000");
  });

  it("can explicitly suppress idempotency keys", async () => {
    const fetch = vi.fn(async () => jsonResponse({ id: "col" }, { status: 201 }));
    const client = new RagComputer({ baseUrl: "http://api.local", fetch });

    await client._request("DELETE", "/v1/collections/docs", { idempotencyKey: null });

    const init = (fetch.mock.calls as unknown as Array<[string, RequestInit]>)[0][1];
    expect(init.headers).not.toHaveProperty("Idempotency-Key");
  });

  it("maps empty and no-content responses to ok status", async () => {
    const noContent = new RagComputer({
      baseUrl: "http://api.local",
      fetch: vi.fn(async () => new Response(null, { status: 204 })),
    });
    const empty = new RagComputer({
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
    const client = new RagComputer({
      apiKey: "ragc_sk_test",
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
        Authorization: "Bearer ragc_sk_test",
        "Idempotency-Key": "idem_upload",
      }),
    );
    expect(init.headers).not.toHaveProperty("Content-Type");
  });

  it("maps structured error bodies to typed errors", async () => {
    const cases: Array<[number, new (...args: never[]) => Error]> = [
      [400, BadRequestError],
      [401, AuthenticationError],
      [404, NotFoundError],
      [429, RateLimitError],
      [500, InternalServerError],
    ];

    for (const [status, errorClass] of cases) {
      const fetch = vi.fn(async () => jsonResponse({ detail: `status ${status}` }, { status }));
      const client = new RagComputer({ baseUrl: "http://api.local", fetch, maxRetries: 0 });

      await expect(client.health()).rejects.toBeInstanceOf(errorClass);
    }
  });

  it("falls back to status text when error bodies are not JSON", async () => {
    const fetch = vi.fn(
      async () => new Response("not-json", { status: 418, statusText: "Teapot" }),
    );
    const client = new RagComputer({ baseUrl: "http://api.local", fetch, maxRetries: 0 });

    await expect(client.health()).rejects.toMatchObject({
      name: "APIError",
      status: 418,
      message: "Teapot",
    });
  });

  it("maps timeout and connection failures", async () => {
    const timeout = new Error("deadline");
    timeout.name = "TimeoutError";
    const timeoutClient = new RagComputer({
      baseUrl: "http://api.local",
      fetch: vi.fn(async () => {
        throw timeout;
      }),
      maxRetries: 0,
    });

    await expect(timeoutClient.health()).rejects.toBeInstanceOf(APITimeoutError);

    const connectionClient = new RagComputer({
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
    const client = new RagComputer({ baseUrl: "http://api.local", fetch, maxRetries: 1 });

    const result = client.health();
    await vi.advanceTimersByTimeAsync(1000);

    await expect(result).resolves.toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("retries rate limited responses", async () => {
    vi.useFakeTimers();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "slow down" }, { status: 429 }))
      .mockResolvedValueOnce(jsonResponse({ status: "ok" }));
    const client = new RagComputer({ baseUrl: "http://api.local", fetch, maxRetries: 1 });

    const result = client.health();
    await vi.advanceTimersByTimeAsync(1000);

    await expect(result).resolves.toEqual({ status: "ok" });
    expect(fetch).toHaveBeenCalledTimes(2);
    vi.useRealTimers();
  });

  it("preserves error codes on mapped API errors", () => {
    const error = new APIError(499, "custom", "CUSTOM_CODE");

    expect(error.name).toBe("APIError");
    expect(error.status).toBe(499);
    expect(error.code).toBe("CUSTOM_CODE");
  });
});
