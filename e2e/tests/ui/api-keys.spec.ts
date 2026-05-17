import { expect, test } from "@playwright/test";
import { STORAGE_STATE_PATH, uniqueName } from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

test("mints, rotates, and revokes an API key", async ({ page }) => {
  const keyName = uniqueName("ui-key");

  await page.goto("/api-keys");
  await page.waitForLoadState("domcontentloaded");

  await page.getByRole("button", { name: /new key|create your first key/i }).first().click();

  // The modal renders. Name is required; default access is "full".
  await page.getByLabel("Name").fill(keyName);
  await page.getByRole("button", { name: /create key/i }).click();

  // The "Save this key" modal reveals the secret once. Verify the prefix.
  const secretBlock = page.locator("text=/bigrag_sk_/").first();
  await expect(secretBlock).toBeVisible({ timeout: 15_000 });
  const secretText = (await secretBlock.innerText()).trim();
  expect(secretText.startsWith("bigrag_sk_")).toBeTruthy();

  // Dismiss the secret modal.
  await page.keyboard.press("Escape");

  // The row appears in the keys table.
  const row = page.getByRole("row", { name: new RegExp(keyName) });
  await expect(row).toBeVisible({ timeout: 10_000 });

  // Rotate — the secret modal re-opens with a new key.
  await row.getByRole("button", { name: /^rotate$/i }).click();
  await expect(page.locator("text=/bigrag_sk_/").first()).toBeVisible({
    timeout: 10_000,
  });
  const rotatedText = (
    await page.locator("text=/bigrag_sk_/").first().innerText()
  ).trim();
  expect(rotatedText.startsWith("bigrag_sk_")).toBeTruthy();
  expect(rotatedText).not.toEqual(secretText);
  await page.keyboard.press("Escape");

  // Revoke via the trash icon — confirms via ConfirmDialog.
  await row.getByRole("button", { name: /^delete$/i }).click();
  await page.getByRole("button", { name: /^revoke$/i }).click();

  // Row is gone from the active list.
  await expect(
    page.getByRole("row", { name: new RegExp(keyName) }),
  ).toHaveCount(0, { timeout: 10_000 });
});
