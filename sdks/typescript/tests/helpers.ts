import { BigRAG } from "../src/client.js";

export interface CapturedRequest {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: string | null;
}

export function mockFetch(
  responseBody: unknown = {},
  status = 200,
): { fetch: typeof globalThis.fetch; calls: CapturedRequest[] } {
  const calls: CapturedRequest[] = [];

  const fetch = (async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = typeof input === "string" ? input : input.toString();
    const method = init?.method ?? "GET";
    const headers: Record<string, string> = {};
    if (init?.headers) {
      const h = init.headers as Record<string, string>;
      for (const [k, v] of Object.entries(h)) {
        headers[k] = v;
      }
    }
    let body: string | null = null;
    if (typeof init?.body === "string") {
      body = init.body;
    }

    calls.push({ url, method, headers, body });

    const json = JSON.stringify(responseBody);
    return new Response(json, {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof globalThis.fetch;

  return { fetch, calls };
}

export function createMockClient(
  responseBody: unknown = {},
  status = 200,
  options: { apiKey?: string; baseUrl?: string } = {},
): { client: BigRAG; calls: CapturedRequest[] } {
  const { fetch, calls } = mockFetch(responseBody, status);
  const client = new BigRAG({
    apiKey: options.apiKey ?? "test-key",
    baseUrl: options.baseUrl ?? "http://localhost:6100",
    fetch,
    maxRetries: 0,
  });
  return { client, calls };
}
