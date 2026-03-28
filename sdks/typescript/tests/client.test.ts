import { describe, it } from "node:test";
import assert from "node:assert/strict";

// Import from compiled output
import {
  BigRAG,
  Namespace,
  BigRAGError,
  APIError,
  BadRequestError,
  AuthenticationError,
  NotFoundError,
  RateLimitError,
  InternalServerError,
  ConnectionError,
  TimeoutError,
} from "../dist/index.js";

describe("BigRAG client", () => {
  it("should construct with default options", () => {
    const client = new BigRAG();
    assert.ok(client instanceof BigRAG);
  });

  it("should construct with custom options", () => {
    const client = new BigRAG({
      apiKey: "test-key",
      baseUrl: "http://custom:9090",
      timeout: 5000,
      maxRetries: 1,
    });
    assert.ok(client instanceof BigRAG);
  });

  it("should create namespace handles", () => {
    const client = new BigRAG();
    const ns = client.namespace("test-ns");
    assert.ok(ns instanceof Namespace);
    assert.equal(ns.name, "test-ns");
  });

  it("should strip trailing slashes from base URL", () => {
    const client = new BigRAG({ baseUrl: "http://localhost:8080///" });
    const ns = client.namespace("test");
    assert.ok(ns instanceof Namespace);
  });
});

describe("Error classes", () => {
  it("BigRAGError should be an instance of Error", () => {
    const err = new BigRAGError("test");
    assert.ok(err instanceof Error);
    assert.ok(err instanceof BigRAGError);
    assert.equal(err.message, "test");
    assert.equal(err.name, "BigRAGError");
  });

  it("APIError should have status and optional code", () => {
    const err = new APIError(500, "server error", "INTERNAL");
    assert.ok(err instanceof BigRAGError);
    assert.ok(err instanceof APIError);
    assert.equal(err.status, 500);
    assert.equal(err.message, "server error");
    assert.equal(err.code, "INTERNAL");
  });

  it("BadRequestError should have status 400", () => {
    const err = new BadRequestError("bad");
    assert.equal(err.status, 400);
    assert.equal(err.name, "BadRequestError");
  });

  it("AuthenticationError should have status 401", () => {
    const err = new AuthenticationError("unauth");
    assert.equal(err.status, 401);
    assert.equal(err.name, "AuthenticationError");
  });

  it("NotFoundError should have status 404", () => {
    const err = new NotFoundError("not found");
    assert.equal(err.status, 404);
    assert.equal(err.name, "NotFoundError");
  });

  it("RateLimitError should have status 429", () => {
    const err = new RateLimitError("rate limited");
    assert.equal(err.status, 429);
    assert.equal(err.name, "RateLimitError");
  });

  it("InternalServerError should have status 500", () => {
    const err = new InternalServerError("internal");
    assert.equal(err.status, 500);
    assert.equal(err.name, "InternalServerError");
  });

  it("ConnectionError should be a BigRAGError", () => {
    const err = new ConnectionError("conn failed");
    assert.ok(err instanceof BigRAGError);
    assert.equal(err.name, "ConnectionError");
  });

  it("TimeoutError should be a BigRAGError", () => {
    const err = new TimeoutError("timed out");
    assert.ok(err instanceof BigRAGError);
    assert.equal(err.name, "TimeoutError");
  });

  it("error instanceof checks should work correctly", () => {
    const err = new NotFoundError("missing");
    assert.ok(err instanceof Error);
    assert.ok(err instanceof BigRAGError);
    assert.ok(err instanceof APIError);
    assert.ok(err instanceof NotFoundError);
    assert.ok(!(err instanceof BadRequestError));
  });
});

describe("BigRAG network errors", () => {
  it("should throw ConnectionError on unreachable host", async () => {
    const client = new BigRAG({
      baseUrl: "http://127.0.0.1:1",
      maxRetries: 0,
      timeout: 1000,
    });
    await assert.rejects(
      () => client.health(),
      (err: unknown) => {
        assert.ok(err instanceof ConnectionError);
        return true;
      },
    );
  });
});
