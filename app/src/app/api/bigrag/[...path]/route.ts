import type { NextRequest } from "next/server";

const BIGRAG_URL = process.env.BIGRAG_URL ?? "http://localhost:4000";

const ALLOWED_REQUEST_HEADERS = new Set([
  "accept",
  "accept-encoding",
  "accept-language",
  "authorization",
  "content-type",
  "cookie",
  "idempotency-key",
  "user-agent",
  "if-none-match",
  "if-modified-since",
  "x-requested-with",
]);

const RESPONSE_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
  "content-encoding",
]);

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

const proxy = async (req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) => {
  const { path } = await params;
  const search = req.nextUrl.search;
  const target = `${BIGRAG_URL}/${path.join("/")}${search}`;

  const method = req.method;
  const hasBody = method !== "GET" && method !== "HEAD";

  if (MUTATING_METHODS.has(method)) {
    const origin = req.headers.get("origin");
    const host = req.headers.get("host");
    if (!origin) {
      return new Response(JSON.stringify({ detail: "Missing Origin header on mutating request" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      });
    }
    let originHost: string;
    try {
      originHost = new URL(origin).host;
    } catch {
      return new Response(JSON.stringify({ detail: "Malformed Origin header" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      });
    }
    if (originHost !== host) {
      return new Response(JSON.stringify({ detail: "Cross-origin request rejected" }), {
        status: 403,
        headers: { "content-type": "application/json" },
      });
    }
  }

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (ALLOWED_REQUEST_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: hasBody ? req.body : undefined,
      redirect: "manual",
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch {
    return new Response(
      JSON.stringify({ detail: "bigRAG API is not reachable", upstream: BIGRAG_URL }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!RESPONSE_HOP_HEADERS.has(key.toLowerCase())) {
      responseHeaders.append(key, value);
    }
  });

  if (upstream.status >= 300 && upstream.status < 400) {
    const location = responseHeaders.get("location");
    if (location) {
      try {
        const resolved = new URL(location, BIGRAG_URL);
        if (resolved.origin !== new URL(BIGRAG_URL).origin) {
          responseHeaders.delete("location");
        }
      } catch {
        responseHeaders.delete("location");
      }
    }
  }

  const isStream = (upstream.headers.get("content-type") ?? "").includes("text/event-stream");
  const body = isStream ? upstream.body : await upstream.arrayBuffer();

  return new Response(body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
};

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as HEAD,
  proxy as OPTIONS,
};
