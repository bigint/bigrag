import { APIConnectionError, APITimeoutError, errorForStatus } from "./errors.js";

const DEFAULT_BASE_URL = "http://localhost:6100";
const DEFAULT_TIMEOUT = 120_000;
const DEFAULT_MAX_RETRIES = 2;

/** @internal */
export const USER_AGENT = "bigrag-typescript/0.0.1";

/** Options accepted by the {@link BigRAGCore} constructor. */
export interface BigRAGOptions {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  fetch?: typeof globalThis.fetch;
}

/**
 * Internal interface that resource classes use to issue HTTP requests.
 *
 * This decouples resources from the concrete BigRAGCore implementation so
 * they only depend on the transport surface.
 */
export interface RequestClient {
  /** Issue a JSON-based HTTP request and return the parsed response body. */
  _request<T>(
    method: string,
    path: string,
    opts?: { json?: unknown; params?: Record<string, string> },
  ): Promise<T>;

  /** Issue a `multipart/form-data` POST and return the parsed response body. */
  _requestFormData<T>(path: string, formData: FormData): Promise<T>;

  /** The base URL of the API server (no trailing slash). */
  readonly baseUrl: string;

  /** The API key used for authentication. */
  readonly apiKey: string;

  /** The configured fetch implementation. */
  readonly _fetch: typeof globalThis.fetch;
}

/**
 * Low-level HTTP transport for the bigRAG API.
 *
 * Handles authentication headers, retries with exponential back-off,
 * timeout via `AbortSignal.timeout`, and error classification.
 */
export class BigRAGCore implements RequestClient {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeout: number;
  readonly maxRetries: number;
  readonly _fetch: typeof globalThis.fetch;

  constructor(options: BigRAGOptions = {}) {
    this.apiKey =
      options.apiKey ??
      (typeof process !== "undefined"
        ? ((process.env as Record<string, string | undefined>).BIGRAG_API_KEY ?? "")
        : "");
    this.baseUrl = (options.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeout = options.timeout ?? DEFAULT_TIMEOUT;
    this.maxRetries = options.maxRetries ?? DEFAULT_MAX_RETRIES;
    this._fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  /** @internal Build standard request headers including auth. */
  _headers(): Record<string, string> {
    const h: Record<string, string> = {
      "User-Agent": USER_AGENT,
    };
    if (this.apiKey) h.Authorization = `Bearer ${this.apiKey}`;
    return h;
  }

  /** @internal Fetch with retry and exponential back-off. */
  async _fetchWithRetry(url: string, init: RequestInit): Promise<Response> {
    let lastError: Error | undefined;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      if (attempt > 0) {
        await sleep(Math.min(0.5 * 2 ** attempt, 4) * 1000);
      }

      let response: Response;
      try {
        response = await this._fetch(url, {
          ...init,
          signal: AbortSignal.timeout(this.timeout),
        });
      } catch (err) {
        lastError = err instanceof Error ? err : new Error(String(err));
        if (lastError.name === "TimeoutError" || lastError.name === "AbortError") {
          if (attempt < this.maxRetries) continue;
          throw new APITimeoutError(lastError.message);
        }
        if (attempt < this.maxRetries) continue;
        throw new APIConnectionError(lastError.message);
      }

      if (response.status >= 500 && attempt < this.maxRetries) {
        lastError = new Error(await response.text().catch(() => "Server error"));
        continue;
      }

      if (response.status === 429 && attempt < this.maxRetries) {
        lastError = new Error("Rate limited");
        continue;
      }

      if (response.status >= 400) {
        await this._throwForStatus(response);
      }

      return response;
    }

    throw new APIConnectionError(lastError?.message ?? "Request failed");
  }

  /** @internal Parse an error response and throw the appropriate error class. */
  async _throwForStatus(response: Response): Promise<never> {
    let errBody: {
      detail?: string;
      error?: { message?: string; code?: string };
      message?: string;
    };
    try {
      errBody = await response.json();
    } catch {
      errBody = {};
    }
    const message =
      errBody.detail ?? errBody.error?.message ?? errBody.message ?? response.statusText;
    const code = errBody.error?.code;
    throw errorForStatus(response.status, message, code);
  }

  /** Issue a JSON-based HTTP request and return the parsed response body. */
  async _request<T>(
    method: string,
    path: string,
    opts?: { json?: unknown; params?: Record<string, string> },
  ): Promise<T> {
    let url = `${this.baseUrl}${path}`;
    if (opts?.params) {
      url += `?${new URLSearchParams(opts.params)}`;
    }

    const headers: Record<string, string> = { ...this._headers() };
    let body: string | undefined;
    if (opts?.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(opts.json);
    }

    const response = await this._fetchWithRetry(url, { method, headers, body });

    if (response.status === 204) return { status: "ok" } as T;
    const text = await response.text();
    if (!text) return { status: "ok" } as T;
    return JSON.parse(text) as T;
  }

  /** Issue a `multipart/form-data` POST and return the parsed response body. */
  async _requestFormData<T>(path: string, formData: FormData): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const response = await this._fetchWithRetry(url, {
      method: "POST",
      headers: this._headers(),
      body: formData,
    });
    return (await response.json()) as T;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
