import { expect, test } from "@playwright/test";
import {
  STORAGE_STATE_PATH,
  deleteCollectionViaApi,
  ensureEmbeddingPreset,
  newRequestContext,
  uniqueName,
} from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

test.describe("collection CRUD", () => {
  test("creates a collection from the UI and opens its detail page", async ({
    page,
  }) => {
    // Make sure an embedding preset exists — the create-collection modal
    // requires one before its submit button is enabled.
    const api = await newRequestContext();
    try {
      await ensureEmbeddingPreset(api);
    } finally {
      await api.dispose();
    }

    const name = uniqueName("ui");

    await page.goto("/collections");
    await page.getByRole("button", { name: /new collection/i }).first().click();

    // The modal renders Name + form. Fill the Name field.
    await page.getByLabel("Name").fill(name);

    await page
      .getByRole("button", { name: /create collection/i })
      .click();

    // Modal closes and the row appears in the collections table.
    await expect(page.getByRole("link", { name })).toBeVisible({
      timeout: 15_000,
    });

    // Navigate into the collection.
    await page.getByRole("link", { name }).first().click();
    await page.waitForURL(new RegExp(`/collections/${name}$`));
    await expect(
      page.getByRole("heading", { name, exact: false }),
    ).toBeVisible();

    // Visit settings, edit description, save.
    await page.getByRole("link", { name: /settings/i }).first().click();
    await page.waitForURL(/\/settings$/);
    const description = page.getByLabel("Description");
    await expect(description).toBeVisible();
    await description.fill("edited via e2e");
    await page.getByRole("button", { name: /save defaults/i }).click();
    // Toast or persisted description on reload — re-fetch and verify it sticks.
    await page.reload();
    await expect(page.getByLabel("Description")).toHaveValue("edited via e2e");

    // Delete the collection from the danger zone.
    await page
      .getByRole("button", { name: /delete collection/i })
      .first()
      .click();
    const confirmInput = page.getByLabel(new RegExp(`type ${name}`, "i"));
    await confirmInput.fill(name);
    await page
      .getByRole("button", { name: /delete collection/i })
      .last()
      .click();

    await page.waitForURL(/\/collections\/?$/, { timeout: 15_000 });
    await expect(page.getByRole("link", { name })).toHaveCount(0);

    // Clean up just in case (idempotent).
    const cleanup = await newRequestContext();
    try {
      await deleteCollectionViaApi(cleanup, name);
    } finally {
      await cleanup.dispose();
    }
  });
});
