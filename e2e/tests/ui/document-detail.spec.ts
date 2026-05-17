import { expect, test } from "@playwright/test";
import {
  STORAGE_STATE_PATH,
  createCollectionViaApi,
  deleteCollectionViaApi,
  newRequestContext,
  uploadDocViaApi,
} from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

test("renders document chunks and triggers reprocess", async ({ page }) => {
  const api = await newRequestContext();
  let collectionName = "";
  try {
    const collection = await createCollectionViaApi(api);
    collectionName = collection.name;
    const doc = await uploadDocViaApi(api, collectionName, "sample.txt", {
      timeoutMs: 90_000,
    });
    expect(doc.status).toBe("ready");

    await page.goto(`/collections/${collectionName}/documents/${doc.id}`);
    await page.waitForLoadState("domcontentloaded");

    // Document filename appears in the header.
    await expect(
      page.getByRole("heading", { name: doc.filename }),
    ).toBeVisible();

    // Chunks section heading is present.
    await expect(
      page.getByRole("heading", { name: /^chunks$/i }),
    ).toBeVisible();

    // At least one chunk article appears (index #0).
    await expect(page.locator('article[id^="chunk-"]').first()).toBeVisible({
      timeout: 30_000,
    });

    // Click Reprocess — this should kick the document back into processing.
    await page.getByRole("button", { name: /reprocess/i }).click();

    // After reprocess, the status badge transitions away from ready.
    await expect
      .poll(
        async () => {
          const text = (await page.locator("body").innerText()) || "";
          return text.toLowerCase();
        },
        { message: "reprocess never re-entered a non-ready state", timeout: 30_000 },
      )
      .toMatch(/processing|pending|queued|ingesting/);
  } finally {
    if (collectionName) await deleteCollectionViaApi(api, collectionName);
    await api.dispose();
  }
});
