import type { NextRequest } from "next/server";

const BIGRAG_URL = process.env.BIGRAG_URL ?? "http://localhost:6100";

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
]);

const proxy = async (req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) => {
  const { path } = await params;
  const search = req.nextUrl.search;
  const target = `${BIGRAG_URL}/${path.join("/")}${search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_HEADERS.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });

  const method = req.method;
  const body =
    method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();

  const upstream = await fetch(target, {
    method,
    headers,
    body,
    redirect: "manual",
    // @ts-expect-error — duplex is required on Node 18+ for streaming bodies
    duplex: "half",
  });

  const responseHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP_HEADERS.has(key.toLowerCase())) {
      responseHeaders.append(key, value);
    }
  });

  return new Response(upstream.body, {
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
