import { describe, it, expect } from "vitest";
import {
  APIError,
  AuthenticationError,
  BadRequestError,
  NotFoundError,
  RateLimitError,
  InternalServerError,
  APIConnectionError,
  APITimeoutError,
  BigRAGError,
  errorForStatus,
} from "../src/errors.js";
import { createMockClient } from "./helpers.js";
import { BigRAG } from "../src/client.js";

// ---------------------------------------------------------------------------
// Error classes
// ---------------------------------------------------------------------------

describe("error classes", () => {
  it("BigRAGError is instanceof Error", () => {
    const err = new BigRAGError("test");
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("BigRAGError");
    expect(err.message).toBe("test");
  });

  it("APIError has status and code", () => {
    const err = new APIError(418, "teapot", "TEAPOT");
    expect(err.status).toBe(418);
    expect(err.code).toBe("TEAPOT");
    expect(err.message).toBe("teapot");
    expect(err).toBeInstanceOf(BigRAGError);
  });

  it("BadRequestError is 400", () => {
    const err = new BadRequestError("bad");
    expect(err.status).toBe(400);
    expect(err.name).toBe("BadRequestError");
  });

  it("AuthenticationError is 401", () => {
    expect(new AuthenticationError("no auth").status).toBe(401);
  });

  it("NotFoundError is 404", () => {
    expect(new NotFoundError("not found").status).toBe(404);
  });

  it("RateLimitError is 429", () => {
    expect(new RateLimitError("slow down").status).toBe(429);
  });

  it("InternalServerError is 500", () => {
    expect(new InternalServerError("oops").status).toBe(500);
  });

  it("APIConnectionError", () => {
    const err = new APIConnectionError("refused");
    expect(err).toBeInstanceOf(BigRAGError);
    expect(err.name).toBe("APIConnectionError");
  });

  it("APITimeoutError has default message", () => {
    const err = new APITimeoutError();
    expect(err.message).toBe("Request timed out");
    expect(err.name).toBe("APITimeoutError");
  });
});

// ---------------------------------------------------------------------------
// errorForStatus
// ---------------------------------------------------------------------------

describe("errorForStatus", () => {
  it("returns BadRequestError for 400", () => {
    expect(errorForStatus(400, "bad")).toBeInstanceOf(BadRequestError);
  });

  it("returns AuthenticationError for 401", () => {
    expect(errorForStatus(401, "unauth")).toBeInstanceOf(AuthenticationError);
  });

  it("returns NotFoundError for 404", () => {
    expect(errorForStatus(404, "gone")).toBeInstanceOf(NotFoundError);
  });

  it("returns RateLimitError for 429", () => {
    expect(errorForStatus(429, "slow")).toBeInstanceOf(RateLimitError);
  });

  it("returns InternalServerError for 500", () => {
    expect(errorForStatus(500, "boom")).toBeInstanceOf(InternalServerError);
  });

  it("returns generic APIError for unknown status", () => {
    const err = errorForStatus(418, "teapot");
    expect(err).toBeInstanceOf(APIError);
    expect(err).not.toBeInstanceOf(BadRequestError);
    expect(err.status).toBe(418);
  });

  it("preserves error code", () => {
    expect(errorForStatus(400, "bad", "VALIDATION").code).toBe("VALIDATION");
  });
});

// ---------------------------------------------------------------------------
// HTTP error handling in client
// ---------------------------------------------------------------------------

describe("HTTP error responses", () => {
  it("throws NotFoundError on 404", async () => {
    const { client } = createMockClient({ detail: "Collection not found" }, 404);
    await expect(client.getCollection("missing")).rejects.toThrow(NotFoundError);
  });

  it("throws AuthenticationError on 401", async () => {
    const { client } = createMockClient({ detail: "Invalid token" }, 401);
    await expect(client.listCollections()).rejects.toThrow(AuthenticationError);
  });

  it("throws BadRequestError on 400", async () => {
    const { client } = createMockClient({ detail: "Invalid name" }, 400);
    await expect(client.createCollection({ name: "bad!" })).rejects.toThrow(BadRequestError);
  });

  it("parses detail from response body", async () => {
    const { client } = createMockClient({ detail: "Collection not found" }, 404);
    try {
      await client.getCollection("missing");
    } catch (err) {
      expect(err).toBeInstanceOf(NotFoundError);
      expect((err as NotFoundError).message).toBe("Collection not found");
    }
  });

  it("parses error.message and error.code from response body", async () => {
    const { client } = createMockClient(
      { error: { message: "custom error", code: "CUSTOM" } },
      400,
    );
    try {
      await client.listCollections();
    } catch (err) {
      expect(err).toBeInstanceOf(BadRequestError);
      expect((err as BadRequestError).message).toBe("custom error");
      expect((err as BadRequestError).code).toBe("CUSTOM");
    }
  });

  it("throws APIConnectionError on network failure", async () => {
    const fetch = (async () => {
      throw new Error("ECONNREFUSED");
    }) as typeof globalThis.fetch;

    const client = new BigRAG({ apiKey: "key", fetch, maxRetries: 0 });
    await expect(client.health()).rejects.toThrow(APIConnectionError);
  });

  it("throws RateLimitError on 429 with no retries", async () => {
    const { client } = createMockClient({ detail: "Too many requests" }, 429);
    await expect(client.listCollections()).rejects.toThrow(RateLimitError);
  });

  it("throws InternalServerError on 500 with no retries", async () => {
    const { client } = createMockClient({ detail: "Server error" }, 500);
    await expect(client.listCollections()).rejects.toThrow(InternalServerError);
  });
});
