import { expect, test } from "@playwright/test";
import { newRequestContext } from "./helpers";

// The first-run admin setup is one-shot: global-setup creates the admin if
// the database is fresh, so by the time UI tests run, /auth/setup must
// redirect away. This spec verifies that redirect contract and the
// API-level setup-status flag the redirect depends on.
test.describe("auth setup", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("setup-status reports needs_setup=false once admin exists", async () => {
    const request = await newRequestContext();
    try {
      const resp = await request.get("/v1/auth/setup-status");
      expect(resp.ok()).toBeTruthy();
      const body = await resp.json();
      expect(body).toHaveProperty("needs_setup");
      expect(body.needs_setup).toBe(false);
    } finally {
      await request.dispose();
    }
  });

  test("visiting /setup with admin present redirects to /login", async ({
    page,
  }) => {
    await page.goto("/setup");
    await page.waitForURL((url) => url.pathname === "/login", {
      timeout: 10_000,
    });
    await expect(
      page.getByRole("heading", { name: /sign in/i }),
    ).toBeVisible();
  });

  test("root path redirects unauthenticated visitors to /login", async ({
    page,
  }) => {
    await page.goto("/");
    await page.waitForURL((url) => url.pathname === "/login", {
      timeout: 10_000,
    });
    await expect(
      page.getByRole("heading", { name: /sign in/i }),
    ).toBeVisible();
  });
});
