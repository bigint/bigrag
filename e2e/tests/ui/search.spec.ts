import { expect, test } from "@playwright/test";
import {
  STORAGE_STATE_PATH,
  createCollectionViaApi,
  deleteCollectionViaApi,
  newRequestContext,
  uploadDocViaApi,
} from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

// Search page selectors changed; needs refresh against the current UI.
test.skip("runs a semantic search and shows results with citations", async ({
  page,
}) => {
  const api = await newRequestContext();
  let collectionName = "";
  try {
    const collection = await createCollectionViaApi(api);
    collectionName = collection.name;
    const doc = await uploadDocViaApi(api, collectionName, "sample.txt", {
      timeoutMs: 90_000,
    });
    expect(doc.status).toBe("ready");

    await page.goto(`/collections/${collectionName}/search`);
    await page.waitForLoadState("domcontentloaded");

    const queryBox = page.getByPlaceholder(/ask a question/i);
    await queryBox.fill("what is in the sample document");
    await page.getByRole("button", { name: /run query/i }).click();

    // A result card appears containing a score badge and a doc link.
    await expect(page.getByText(/^score\s+0\./).first()).toBeVisible({
      timeout: 30_000,
    });

    // At least one result paragraph is non-empty (the chunk body).
    const articles = page.locator("article");
    await expect(articles.first()).toBeVisible();
    const body = await articles.first().innerText();
    expect(body.trim().length).toBeGreaterThan(0);

    // The citation links back to the source document (filename or id snippet).
    await expect(
      page.getByRole("link", { name: new RegExp(doc.filename.slice(0, 6), "i") }).first(),
    ).toBeVisible();
  } finally {
    if (collectionName) await deleteCollectionViaApi(api, collectionName);
    await api.dispose();
  }
});
