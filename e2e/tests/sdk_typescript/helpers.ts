import { randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { BigRAG } from "@bigrag/client";
import type {
  Collection,
  CreateApiKeyResponse,
  CreateCollectionBody,
  Document,
} from "@bigrag/client";

export const API_BASE = process.env.BIGRAG_E2E_API_BASE ?? "http://localhost:4000";

export const ADMIN_EMAIL = process.env.BIGRAG_E2E_ADMIN_EMAIL ?? "e2e-admin@example.com";
export const ADMIN_PASSWORD =
  process.env.BIGRAG_E2E_ADMIN_PASSWORD ?? "e2e-admin-password-123!";
export const ADMIN_DISPLAY_NAME =
  process.env.BIGRAG_E2E_ADMIN_DISPLAY_NAME ?? "E2E Admin";

const FIXTURES_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../fixtures/documents");

const createdApiKeyIds: string[] = [];
const createdCollectionNames: string[] = [];

let cachedAdminSessionCookie: string | undefined;

export function uniqueName(prefix: string = "e2e"): string {
  return `${prefix}_${randomBytes(3).toString("hex")}`;
}

interface FetchInit extends RequestInit {
  headers?: Record<string, string>;
}

async function rawFetch(path: string, init: FetchInit = {}): Promise<Response> {
  const headers: Record<string, string> = { ...(init.headers ?? {}) };
  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

async function ensureAdminExists(): Promise<void> {
  const status = await rawFetch("/v1/auth/setup-status");
  if (!status.ok) {
    throw new Error(`setup-status failed: ${status.status} ${await status.text()}`);
  }
  const body = (await status.json()) as { needs_setup?: boolean };
  if (!body.needs_setup) return;

  const setup = await rawFetch("/v1/auth/setup", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: API_BASE,
    },
    body: JSON.stringify({
      email: ADMIN_EMAIL,
      password: ADMIN_PASSWORD,
      display_name: ADMIN_DISPLAY_NAME,
    }),
  });
  if (setup.status !== 200 && setup.status !== 201) {
    throw new Error(`admin setup failed: ${setup.status} ${await setup.text()}`);
  }
}

async function getAdminSessionCookie(): Promise<string> {
  if (cachedAdminSessionCookie) return cachedAdminSessionCookie;
  await ensureAdminExists();
  const resp = await rawFetch("/v1/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: API_BASE,
    },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });
  if (resp.status !== 200) {
    throw new Error(`admin login failed: ${resp.status} ${await resp.text()}`);
  }
  const setCookie = resp.headers.get("set-cookie");
  if (!setCookie) {
    throw new Error("admin login did not return a set-cookie header");
  }
  const cookie = setCookie
    .split(",")
    .map((s) => s.trim())
    .map((s) => s.split(";")[0])
    .filter(Boolean)
    .join("; ");
  cachedAdminSessionCookie = cookie;
  return cookie;
}

export async function adminSessionFetch(
  path: string,
  init: FetchInit = {},
): Promise<Response> {
  const cookie = await getAdminSessionCookie();
  const mutating = ["POST", "PUT", "PATCH", "DELETE"].includes(
    (init.method ?? "GET").toUpperCase(),
  );
  const headers: Record<string, string> = {
    ...(init.headers ?? {}),
    Cookie: cookie,
  };
  if (mutating && !headers.Origin) headers.Origin = API_BASE;
  return rawFetch(path, { ...init, headers });
}

export interface MintApiKeyOptions {
  name?: string;
  scopes?: string[] | null;
  collection?: string | null;
  expires_at?: string | null;
}

export interface MintedApiKey {
  id: string;
  key: string;
  name: string;
  scopes: string[];
  collection: string | null;
}

export async function mintApiKey(options: MintApiKeyOptions = {}): Promise<MintedApiKey> {
  const payload: Record<string, unknown> = { name: options.name ?? uniqueName("sdk-key") };
  if (options.scopes !== undefined) payload.scopes = options.scopes;
  if (options.collection !== undefined) payload.collection = options.collection;
  if (options.expires_at !== undefined) payload.expires_at = options.expires_at;

  const resp = await adminSessionFetch("/v1/admin/api-keys", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (resp.status !== 201) {
    throw new Error(`mintApiKey failed: ${resp.status} ${await resp.text()}`);
  }
  const data = (await resp.json()) as CreateApiKeyResponse;
  createdApiKeyIds.push(data.id);
  return {
    id: data.id,
    key: data.key,
    name: data.name,
    scopes: data.scopes,
    collection: data.collection,
  };
}

export async function cleanupApiKeys(): Promise<void> {
  while (createdApiKeyIds.length > 0) {
    const id = createdApiKeyIds.pop();
    if (!id) continue;
    try {
      await adminSessionFetch(`/v1/admin/api-keys/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
    } catch {
      /* ignore teardown errors */
    }
  }
}

export interface AdminClientResult {
  client: BigRAG;
  key: MintedApiKey;
}

export async function getAdminClient(): Promise<AdminClientResult> {
  const key = await mintApiKey({ name: uniqueName("sdk-admin"), scopes: ["*:*"] });
  const client = new BigRAG({
    apiKey: key.key,
    baseUrl: API_BASE,
    maxRetries: 0,
  });
  return { client, key };
}

export function buildClient(apiKey: string, overrides: Partial<{ baseUrl: string }> = {}): BigRAG {
  return new BigRAG({
    apiKey,
    baseUrl: overrides.baseUrl ?? API_BASE,
    maxRetries: 0,
  });
}

export async function createCollection(
  client: BigRAG,
  overrides: Partial<CreateCollectionBody> = {},
): Promise<Collection> {
  const body: CreateCollectionBody = {
    name: overrides.name ?? uniqueName("e2e"),
    description: overrides.description ?? "sdk e2e collection",
    vector_store_provider: overrides.vector_store_provider ?? "qdrant",
    chunk_size: overrides.chunk_size ?? 512,
    chunk_overlap: overrides.chunk_overlap ?? 50,
    chunk_strategy: overrides.chunk_strategy ?? "paragraph",
    reranking_enabled: overrides.reranking_enabled ?? false,
    default_top_k: overrides.default_top_k ?? 10,
    default_search_mode: overrides.default_search_mode ?? "semantic",
    ...overrides,
  };
  const created = await client.collections.create(body);
  createdCollectionNames.push(created.name);
  return created;
}

export async function cleanupCollections(): Promise<void> {
  while (createdCollectionNames.length > 0) {
    const name = createdCollectionNames.pop();
    if (!name) continue;
    try {
      await adminSessionFetch(`/v1/collections/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
    } catch {
      /* ignore */
    }
  }
}

export function fixturePath(name: string): string {
  return join(FIXTURES_DIR, name);
}

export async function readFixture(name: string): Promise<Buffer> {
  return await readFile(fixturePath(name));
}

export interface UploadFixtureOptions {
  filename?: string;
  metadata?: Record<string, unknown>;
  wait?: boolean;
  timeoutMs?: number;
  terminalStatuses?: ReadonlySet<string>;
}

export async function uploadFixture(
  client: BigRAG,
  collectionName: string,
  fixture: string,
  options: UploadFixtureOptions = {},
): Promise<Document> {
  const content = await readFixture(fixture);
  const filename = options.filename ?? fixture;
  const doc = await client.documents.upload(
    collectionName,
    { path: fixturePath(fixture), name: filename },
    options.metadata,
  );
  if (options.wait === false) return doc;
  const terminal = options.terminalStatuses ?? new Set(["ready", "failed"]);
  return await waitForDocument(client, collectionName, doc.id, {
    timeoutMs: options.timeoutMs,
    terminal,
  });
}

export interface WaitForDocumentOptions {
  timeoutMs?: number;
  intervalMs?: number;
  terminal?: ReadonlySet<string>;
}

export async function waitForDocument(
  client: BigRAG,
  collectionName: string,
  documentId: string,
  options: WaitForDocumentOptions = {},
): Promise<Document> {
  const timeoutMs = options.timeoutMs ?? 60_000;
  const intervalMs = options.intervalMs ?? 500;
  const terminal = options.terminal ?? new Set(["ready", "failed"]);
  const deadline = Date.now() + timeoutMs;
  let last: Document | null = null;
  while (Date.now() < deadline) {
    last = await client.documents.get(collectionName, documentId);
    if (terminal.has(last.status)) return last;
    await sleep(intervalMs);
  }
  throw new Error(
    `document ${documentId} did not reach terminal status in ${timeoutMs}ms; last=${JSON.stringify(last)}`,
  );
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
