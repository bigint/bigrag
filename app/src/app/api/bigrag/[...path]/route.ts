import type { NextRequest } from "next/server";

const BIGRAG_URL = process.env.BIGRAG_URL ?? "http://localhost:6100";

// Headers that must not be forwarded on either direction of a proxy.
const HOP_HEADERS = new Set([
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
  // Node's fetch auto-decodes gzip/deflate/br response bodies, so
  // forwarding the original encoding header would mislead the browser
  // into trying to decode a plaintext body.
  "content-encoding",
]);

const proxy = async (req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) => {
  const { path } = await params;
  const search = req.nextUrl.search;
  const target = `${BIGRAG_URL}/${path.join("/")}${search}`;

  const method = req.method;
  const hasBody = method !== "GET" && method !== "HEAD";

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      // duplex is required only when streaming a request body
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch (err) {
    console.error(`[bigrag-proxy] upstream unreachable: ${target}`, err);
    return new Response(
      JSON.stringify({ detail: "bigRAG API is not reachable", upstream: BIGRAG_URL }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_HEADERS.has(key.toLowerCase())) {
      responseHeaders.append(key, value);
    }
  });

  // SSE / event-stream endpoints must stream — buffering would break the
  // document-progress and collection-events routes.
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
