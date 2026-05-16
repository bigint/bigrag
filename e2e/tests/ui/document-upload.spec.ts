import { expect, test } from "@playwright/test";
import {
  STORAGE_STATE_PATH,
  createCollectionViaApi,
  deleteCollectionViaApi,
  fixturePath,
  newRequestContext,
} from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

test("uploads a document via the UI and shows it as ready", async ({
  page,
}) => {
  const api = await newRequestContext();
  let collectionName = "";
  try {
    const collection = await createCollectionViaApi(api);
    collectionName = collection.name;

    await page.goto(`/collections/${collectionName}/documents`);
    await page.waitForLoadState("networkidle");

    // The upload dropzone has a sr-only file input keyed by id "doc-upload".
    const fileInput = page.locator("input#doc-upload");
    await fileInput.setInputFiles(fixturePath("sample.pdf"));

    // The filename appears in the documents list once ingestion lands.
    const row = page.getByText("sample.pdf").first();
    await expect(row).toBeVisible({ timeout: 30_000 });

    // Eventually the row should reach "ready" status.
    await expect
      .poll(
        async () => {
          const handle = page.locator("li", { hasText: "sample.pdf" }).first();
          const text = (await handle.innerText().catch(() => "")) || "";
          return text.toLowerCase();
        },
        { message: "document never reached ready status", timeout: 60_000 },
      )
      .toMatch(/ready/);
  } finally {
    if (collectionName) await deleteCollectionViaApi(api, collectionName);
    await api.dispose();
  }
});
