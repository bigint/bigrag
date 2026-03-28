import { Namespace } from "./namespace.js";
import {
  BigRAGError,
  ConnectionError,
  TimeoutError,
  RateLimitError,
  errorForStatus,
} from "./errors.js";
import type { NamespaceListResponse } from "./types.js";

/**
 * Options for constructing a BigRAG client.
 */
export interface BigRAGOptions {
  /** API key for authentication. Falls back to BIGRAG_API_KEY env var. */
  apiKey?: string;
  /** Base URL of the bigRAG server. Defaults to http://localhost:8080. */
  baseUrl?: string;
  /** Request timeout in milliseconds. Defaults to 30000 (30s). */
  timeout?: number;
  /** Maximum number of retries on transient failures. Defaults to 3. */
  maxRetries?: number;
}

/**
 * BigRAG client for interacting with the bigRAG vector + full-text search database.
 *
 * @example
 * ```ts
 * const client = new BigRAG({ apiKey: "my-key" });
 * const ns = client.namespace("my-namespace");
 * await ns.upsert([{ id: 1, vector: [0.1, 0.2], title: "hello" }]);
 * ```
 */
export class BigRAG {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly maxRetries: number;

  constructor(options: BigRAGOptions = {}) {
    this.apiKey = options.apiKey ?? process.env.BIGRAG_API_KEY ?? "";
    this.baseUrl = (options.baseUrl ?? "http://localhost:8080").replace(/\/+$/, "");
    this.timeout = options.timeout ?? 30_000;
    this.maxRetries = options.maxRetries ?? 3;
  }

  /**
   * Get a Namespace handle for performing operations on a specific namespace.
   */
  namespace(name: string): Namespace {
    return new Namespace(this, name);
  }

  /**
   * List namespaces with optional filtering and pagination.
   */
  async namespaces(options?: {
    prefix?: string;
    cursor?: string;
    pageSize?: number;
  }): Promise<NamespaceListResponse> {
    const params = new URLSearchParams();
    if (options?.prefix) params.set("prefix", options.prefix);
    if (options?.cursor) params.set("cursor", options.cursor);
    if (options?.pageSize) params.set("page_size", String(options.pageSize));

    const qs = params.toString();
    const path = `/v1/namespaces${qs ? `?${qs}` : ""}`;
    return this._request<NamespaceListResponse>("GET", path);
  }

  /**
   * Check server health.
   */
  async health(): Promise<{ status: string; version: string }> {
    return this._request<{ status: string; version: string }>("GET", "/health");
  }

  /**
   * Internal method to make an HTTP request with retries and error handling.
   * @internal
   */
  async _request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": "@bigrag/client/0.1.0",
    };

    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }

    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        // Exponential backoff: 200ms, 400ms, 800ms, ...
        const delay = Math.min(200 * Math.pow(2, attempt - 1), 10_000);
        const jitter = delay * 0.2 * Math.random();
        await sleep(delay + jitter);
      }

      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          method,
          headers,
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        clearTimeout(timer);

        if (response.ok) {
          // Handle 204 No Content
          if (response.status === 204) {
            return undefined as T;
          }
          return (await response.json()) as T;
        }

        // Parse error response
        let errorMessage: string;
        let errorCode: string | undefined;
        try {
          const errorBody = await response.json() as Record<string, unknown>;
          errorMessage = (errorBody.message ?? errorBody.error ?? response.statusText) as string;
          errorCode = errorBody.code as string | undefined;
        } catch {
          errorMessage = response.statusText;
        }

        const error = errorForStatus(response.status, errorMessage, errorCode);

        // Only retry on 429 and 5xx
        if (response.status === 429 || response.status >= 500) {
          lastError = error;
          continue;
        }

        throw error;
      } catch (err) {
        if (err instanceof BigRAGError) {
          // If it's a rate limit error, we already set lastError above
          if (err instanceof RateLimitError) {
            lastError = err;
            continue;
          }
          throw err;
        }

        if (err instanceof DOMException && err.name === "AbortError") {
          lastError = new TimeoutError(
            `Request timed out after ${this.timeout}ms: ${method} ${path}`,
          );
          continue;
        }

        if (err instanceof TypeError) {
          // fetch throws TypeError on network errors
          lastError = new ConnectionError(
            `Failed to connect to ${this.baseUrl}: ${(err as Error).message}`,
          );
          continue;
        }

        lastError = err instanceof Error
          ? new ConnectionError(err.message)
          : new ConnectionError(String(err));
        continue;
      }
    }

    throw lastError ?? new BigRAGError("Request failed after retries");
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
