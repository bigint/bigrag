import { mkdir } from "node:fs/promises";
import { dirname } from "node:path";
import type { FullConfig } from "@playwright/test";
import {
  STORAGE_STATE_PATH,
  apiBase,
  newRequestContext,
  setupOrLoginAdmin,
} from "./helpers";

export default async function globalSetup(_config: FullConfig): Promise<void> {
  await mkdir(dirname(STORAGE_STATE_PATH), { recursive: true });

  const request = await newRequestContext();
  try {
    await setupOrLoginAdmin(request);
    await request.storageState({ path: STORAGE_STATE_PATH });
  } finally {
    await request.dispose();
  }
  process.env.BIGRAG_E2E_API_BASE = apiBase();
}
