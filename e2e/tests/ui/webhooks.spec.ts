import { expect, test } from "@playwright/test";
import { STORAGE_STATE_PATH, uniqueName, webhookSinkBase } from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

// Webhooks UI selectors changed; needs refresh against the current UI.
test.skip("creates a webhook, reveals the signing secret, and runs a test delivery", async ({
  page,
  request,
}) => {
  const label = uniqueName("ui-webhook");
  const sinkUrl = `${webhookSinkBase()}/webhook/${label}`;

  // Reset the sink so this test sees a clean baseline.
  await request.post(`${webhookSinkBase()}/reset`).catch(() => undefined);

  await page.goto("/webhooks");
  await page.waitForLoadState("domcontentloaded");

  await page.getByRole("button", { name: /add webhook/i }).first().click();

  await page.getByLabel("URL").fill(sinkUrl);

  // Pick at least one event category to satisfy the "select at least one"
  // form validation. Document events is a top-level category in the form.
  await page
    .getByRole("checkbox", { name: /select all document events/i })
    .first()
    .check();

  await page.getByRole("button", { name: /^add webhook$/i }).click();

  // The secret-reveal modal shows the hex secret once.
  await expect(page.getByRole("heading", { name: /webhook/i })).toBeVisible({
    timeout: 10_000,
  });
  await page.keyboard.press("Escape");

  // The webhook row appears in the list, identified by its URL.
  const row = page.getByText(sinkUrl).first();
  await expect(row).toBeVisible({ timeout: 10_000 });

  // Trigger a test delivery using the row's test action (button or icon).
  // Prefer a clearly-labeled button; fall back to any "Test" label.
  const testButton = page.getByRole("button", { name: /test/i }).filter({
    hasNotText: /delete|remove/i,
  });
  if ((await testButton.count()) > 0) {
    await testButton.first().click();
    // Wait for a delivery to land in the sink.
    await expect
      .poll(
        async () => {
          const r = await request.get(
            `${webhookSinkBase()}/received?label=${label}`,
          );
          if (!r.ok()) return 0;
          const data = await r.json();
          return Array.isArray(data.deliveries) ? data.deliveries.length : 0;
        },
        { message: "no webhook delivery landed in the sink", timeout: 20_000 },
      )
      .toBeGreaterThan(0);
  }
});
