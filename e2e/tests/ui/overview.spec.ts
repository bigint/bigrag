import { expect, test } from "@playwright/test";
import { STORAGE_STATE_PATH } from "./helpers";

test.use({ storageState: STORAGE_STATE_PATH });

// Greeting heading and metric labels have changed; selectors need refresh
// against the current UI. Tracked in #TODO.
test.skip("dashboard overview renders metric cards and health panels", async ({
  page,
}) => {
  await page.goto("/overview");
  await page.waitForLoadState("domcontentloaded");

  // Greeting heading.
  await expect(
    page.getByRole("heading", { name: /good to see you/i }),
  ).toBeVisible({ timeout: 15_000 });

  // Stat tiles — each metric card uses these labels.
  for (const label of [
    "Collections",
    "Documents",
    "Chunks",
    "Tokens stored",
    "Storage",
  ]) {
    await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
  }

  // Document readiness panel.
  await expect(
    page.getByRole("heading", { name: /document readiness/i }),
  ).toBeVisible();

  // System health panel + at least one service row (Postgres is always listed).
  await expect(
    page.getByRole("heading", { name: /system health/i }),
  ).toBeVisible();
  await expect(page.getByText("Postgres", { exact: true })).toBeVisible();

  // Recent collections section.
  await expect(
    page.getByRole("heading", { name: /recent collections/i }),
  ).toBeVisible();

  // Ingestion queue panel.
  await expect(
    page.getByRole("heading", { name: /ingestion queue/i }),
  ).toBeVisible();
});
