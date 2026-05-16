import { randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { APIRequestContext, Page } from "@playwright/test";
import { expect, request as playwrightRequest } from "@playwright/test";

export const ADMIN_EMAIL = "e2e-admin@example.com";
export const ADMIN_PASSWORD = "e2e-admin-password-123!";
export const ADMIN_DISPLAY_NAME = "E2E Admin";

export const STORAGE_STATE_PATH = "test-results/admin-storage.json";

export const apiBase = (): string =>
  process.env.BIGRAG_E2E_API_BASE ?? "http://localhost:4000";

export const appBase = (): string =>
  process.env.BIGRAG_E2E_APP_BASE ?? "http://localhost:3000";

export const fakeOpenAIBase = (): string =>
  process.env.BIGRAG_E2E_FAKE_OPENAI ?? "http://localhost:9001";

export const fakeOpenAIContainerBase = (): string =>
  process.env.BIGRAG_E2E_FAKE_OPENAI_CONTAINER ?? "http://fake-openai:9001";

export const webhookSinkBase = (): string =>
  process.env.BIGRAG_E2E_WEBHOOK_SINK ?? "http://localhost:9003";

export const fixturesDir = (): string =>
  join(__dirname, "..", "..", "fixtures", "documents");

export const fixturePath = (filename: string): string =>
  join(fixturesDir(), filename);

export const readFixture = (filename: string): Buffer =>
  readFileSync(fixturePath(filename));

export const uniqueName = (prefix = "e2e"): string =>
  `${prefix}_${randomBytes(4).toString("hex")}`;

const originHeaders = (): Record<string, string> => ({
  Origin: apiBase(),
  "Content-Type": "application/json",
});

export const newRequestContext = async (): Promise<APIRequestContext> =>
  playwrightRequest.newContext({
    baseURL: apiBase(),
    extraHTTPHeaders: { Origin: apiBase() },
  });

export const setupOrLoginAdmin = async (
  request: APIRequestContext,
): Promise<void> => {
  const statusResp = await request.get("/v1/auth/setup-status");
  expect(statusResp.ok(), `setup-status failed: ${statusResp.status()}`).toBeTruthy();
  const status = await statusResp.json();
  if (status.needs_setup) {
    const setupResp = await request.post("/v1/auth/setup", {
      data: {
        email: ADMIN_EMAIL,
        password: ADMIN_PASSWORD,
        display_name: ADMIN_DISPLAY_NAME,
      },
      headers: originHeaders(),
    });
    expect(
      setupResp.ok(),
      `setup failed: ${setupResp.status()} ${await setupResp.text()}`,
    ).toBeTruthy();
    return;
  }
  const loginResp = await request.post("/v1/auth/login", {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    headers: originHeaders(),
  });
  expect(
    loginResp.ok(),
    `admin login failed: ${loginResp.status()} ${await loginResp.text()}`,
  ).toBeTruthy();
};

export const ensureEmbeddingPreset = async (
  request: APIRequestContext,
  name = "e2e-default",
): Promise<{ id: string; name: string }> => {
  const list = await request.get("/v1/admin/embedding-presets");
  expect(list.ok()).toBeTruthy();
  const body = await list.json();
  const existing = (body.presets ?? []).find(
    (p: { name: string }) => p.name === name,
  );
  if (existing) return { id: existing.id, name: existing.name };

  const create = await request.post("/v1/admin/embedding-presets", {
    data: {
      name,
      provider: "openai_compatible",
      model: "text-embedding-3-small",
      api_key: "e2e-fake-key",
      base_url: `${fakeOpenAIContainerBase()}/v1`,
      dimension: 1536,
    },
    headers: originHeaders(),
  });
  expect(
    create.ok(),
    `preset create failed: ${create.status()} ${await create.text()}`,
  ).toBeTruthy();
  const preset = await create.json();
  return { id: preset.id, name: preset.name };
};

export interface CreatedCollection {
  id: string;
  name: string;
  embedding_preset_id?: string;
}

export const createCollectionViaApi = async (
  request: APIRequestContext,
  name?: string,
  extras: Record<string, unknown> = {},
): Promise<CreatedCollection> => {
  const preset = await ensureEmbeddingPreset(request);
  const collectionName = name ?? uniqueName("e2e");
  const resp = await request.post("/v1/collections", {
    data: {
      name: collectionName,
      description: "e2e UI collection",
      vector_store_provider: "qdrant",
      chunk_size: 512,
      chunk_overlap: 50,
      chunk_strategy: "paragraph",
      embedding_preset_id: preset.id,
      reranking_enabled: false,
      default_top_k: 10,
      default_search_mode: "semantic",
      ...extras,
    },
    headers: originHeaders(),
  });
  expect(
    resp.ok(),
    `collection create failed: ${resp.status()} ${await resp.text()}`,
  ).toBeTruthy();
  return (await resp.json()) as CreatedCollection;
};

export const deleteCollectionViaApi = async (
  request: APIRequestContext,
  name: string,
): Promise<void> => {
  await request.delete(`/v1/collections/${encodeURIComponent(name)}`, {
    headers: { Origin: apiBase() },
  });
};

export const uploadDocViaApi = async (
  request: APIRequestContext,
  collection: string,
  filename = "sample.txt",
  options: { wait?: boolean; timeoutMs?: number } = {},
): Promise<{ id: string; status: string; filename: string }> => {
  const content = readFixture(filename);
  const resp = await request.post(
    `/v1/collections/${encodeURIComponent(collection)}/documents`,
    {
      multipart: {
        file: {
          name: filename,
          mimeType: "application/octet-stream",
          buffer: content,
        },
      },
      headers: { Origin: apiBase() },
    },
  );
  expect(
    resp.ok(),
    `upload failed: ${resp.status()} ${await resp.text()}`,
  ).toBeTruthy();
  const doc = await resp.json();
  if (options.wait === false) return doc;

  const deadline = Date.now() + (options.timeoutMs ?? 60_000);
  while (Date.now() < deadline) {
    const poll = await request.get(
      `/v1/collections/${encodeURIComponent(collection)}/documents/${doc.id}`,
    );
    if (poll.ok()) {
      const fresh = await poll.json();
      if (fresh.status === "ready" || fresh.status === "failed") return fresh;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`document ${doc.id} did not reach terminal status`);
};

export const loginAsAdmin = async (page: Page): Promise<void> => {
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  if (!page.url().includes("/login")) return;
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), {
    timeout: 15_000,
  });
};

export const sleep = (ms: number): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));
