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
  /**
   * If true (default), mutating requests (POST/PUT/PATCH/DELETE) that
   * don't have an explicit `idempotencyKey` get a random UUID attached.
   * A retried request with the same key replays the first response.
   */
  autoIdempotencyKey?: boolean;
}

/** Per-request options for mutating SDK calls. */
export interface MutatingRequestOptions {
  /**
   * Override the idempotency key for this request. Pass an explicit
   * string to make client retries safe across redeploys; pass `null`
   * to opt out entirely for this call.
   */
  idempotencyKey?: string | null;
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
    opts?: {
      json?: unknown;
      params?: Record<string, string>;
      idempotencyKey?: string | null;
    },
  ): Promise<T>;

  /** Issue a `multipart/form-data` POST and return the parsed response body. */
  _requestFormData<T>(
    path: string,
    formData: FormData,
    opts?: { idempotencyKey?: string | null },
  ): Promise<T>;

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
const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function randomIdempotencyKey(): string {
  // Prefer crypto.randomUUID when available (Node 19+ and modern browsers).
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  if (c?.randomUUID) return c.randomUUID();
  // Fallback: 128 bits of entropy as hex.
  let s = "";
  for (let i = 0; i < 32; i++) s += Math.floor(Math.random() * 16).toString(16);
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}

export class BigRAGCore implements RequestClient {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly timeout: number;
  readonly maxRetries: number;
  readonly _fetch: typeof globalThis.fetch;
  readonly autoIdempotencyKey: boolean;

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
    this.autoIdempotencyKey = options.autoIdempotencyKey ?? true;
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

  /**
   * @internal Resolve the Idempotency-Key for this request.
   *
   * - Explicit string → use as-is.
   * - Explicit null → never send the header.
   * - undefined + mutating verb + autoIdempotencyKey → auto-generate.
   * - undefined + GET/HEAD/OPTIONS → never send.
   */
  _resolveIdempotencyKey(method: string, explicit: string | null | undefined): string | null {
    if (explicit === null) return null;
    if (typeof explicit === "string" && explicit.length > 0) return explicit;
    if (!this.autoIdempotencyKey) return null;
    return MUTATING_METHODS.has(method) ? randomIdempotencyKey() : null;
  }

  /** Issue a JSON-based HTTP request and return the parsed response body. */
  async _request<T>(
    method: string,
    path: string,
    opts?: {
      json?: unknown;
      params?: Record<string, string>;
      idempotencyKey?: string | null;
    },
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
    const idemKey = this._resolveIdempotencyKey(method, opts?.idempotencyKey);
    if (idemKey) headers["Idempotency-Key"] = idemKey;

    const response = await this._fetchWithRetry(url, { method, headers, body });

    if (response.status === 204) return { status: "ok" } as T;
    const text = await response.text();
    if (!text) return { status: "ok" } as T;
    return JSON.parse(text) as T;
  }

  /** Issue a `multipart/form-data` POST and return the parsed response body. */
  async _requestFormData<T>(
    path: string,
    formData: FormData,
    opts?: { idempotencyKey?: string | null },
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = { ...this._headers() };
    const idemKey = this._resolveIdempotencyKey("POST", opts?.idempotencyKey);
    if (idemKey) headers["Idempotency-Key"] = idemKey;
    const response = await this._fetchWithRetry(url, {
      method: "POST",
      headers,
      body: formData,
    });
    return (await response.json()) as T;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
