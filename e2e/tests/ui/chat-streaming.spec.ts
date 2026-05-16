import { expect, test } from "@playwright/test";
import {
  STORAGE_STATE_PATH,
  createCollectionViaApi,
  deleteCollectionViaApi,
  newRequestContext,
  uploadDocViaApi,
} from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

// Chat needs a saved OpenAI API key; the preferences PUT endpoint validates
// that key against api.openai.com regardless of BIGRAG_CHAT_BASE_URL, so the
// fake-openai stub cannot satisfy it from the UI flow alone. We exercise the
// chat shell, collection-selection UX, and the API-key drawer; full token
// streaming is gated behind a real key and is therefore best-effort here.
test("opens the chat shell, selects a collection, and exposes the key drawer", async ({
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

    await page.goto("/chat");
    await page.waitForLoadState("domcontentloaded");

    // The composer textarea is rendered (chat shell loaded).
    await expect(page.getByLabel(/message input/i)).toBeVisible({
      timeout: 30_000,
    });

    // Open the collection picker and choose our test collection.
    const collectionTrigger = page
      .getByRole("button", { name: /(choose collection|^e2e_|^ui_)/i })
      .first();
    await collectionTrigger.click();

    // The CollectionMenu lists every collection by name.
    const option = page.getByRole("menuitem", { name: collectionName }).or(
      page.getByText(collectionName, { exact: true }),
    );
    await option.first().click();

    // Composer placeholder updates to either prompt the user to add a key
    // or to ask a grounded question — both confirm the collection is set.
    await expect(page.getByLabel(/message input/i)).toHaveAttribute(
      "placeholder",
      /(grounded question|openai api key)/i,
      { timeout: 10_000 },
    );

    // Open the API-key drawer.
    await page
      .getByRole("button", { name: /add api key|api key saved/i })
      .first()
      .click();
    // A password/secret field for the OpenAI key is shown in the popover.
    await expect(
      page.locator('input[type="password"], input[placeholder*="sk-" i]').first(),
    ).toBeVisible({ timeout: 5_000 });
  } finally {
    if (collectionName) await deleteCollectionViaApi(api, collectionName);
    await api.dispose();
  }
});
