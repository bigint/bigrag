import { afterAll } from "vitest";
import { cleanupApiKeys, cleanupCollections } from "./helpers.js";

afterAll(async () => {
  await cleanupApiKeys();
  await cleanupCollections();
});
