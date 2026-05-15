import { afterEach, describe, expect, it, vi } from "vitest";

describe("apiClient", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("wraps JSON requests with the configured API base URL", async () => {
    const fetch = vi.fn(async (request: Request) => {
      if (request.body) await request.arrayBuffer();
      return new Response(JSON.stringify({ ok: true }));
    });
    vi.stubGlobal("fetch", fetch);
    const { apiClient } = await import("./api");

    await expect(apiClient.get("/v1/collections", { limit: 5, active: true })).resolves.toEqual({
      ok: true,
    });
    await apiClient.post("/v1/collections", { name: "docs" });
    await apiClient.put("/v1/collections/docs", { display_name: "Docs" });
    await apiClient.patch("/v1/collections/docs", { archived: false });
    await apiClient.delete("/v1/collections/docs");

    const requests = (fetch.mock.calls as unknown as Array<[Request]>).map(([request]) => request);
    expect(requests.map((request) => [request.method, request.url])).toEqual([
      ["GET", "http://localhost:4000/v1/collections?limit=5&active=true"],
      ["POST", "http://localhost:4000/v1/collections"],
      ["PUT", "http://localhost:4000/v1/collections/docs"],
      ["PATCH", "http://localhost:4000/v1/collections/docs"],
      ["DELETE", "http://localhost:4000/v1/collections/docs"],
    ]);
  });

  it("sends form bodies and maps API detail errors", async () => {
    const responses = [
      new Response(JSON.stringify({ uploaded: true })),
      new Response(JSON.stringify({ detail: "Collection missing" }), { status: 404 }),
    ];
    const fetch = vi.fn(async (request: Request) => {
      if (request.body) await request.arrayBuffer();
      return responses.shift() ?? new Response(null, { status: 500 });
    });
    vi.stubGlobal("fetch", fetch);
    const { apiClient } = await import("./api");
    const form = new FormData();
    form.append("file", new Blob(["hello"]), "note.txt");

    await expect(apiClient.postForm("/v1/collections/docs/documents", form)).resolves.toEqual({
      uploaded: true,
    });
    await expect(apiClient.get("/v1/collections/missing")).rejects.toMatchObject({
      name: "HTTPError",
      response: expect.objectContaining({ status: 404 }),
    });
  });
});
