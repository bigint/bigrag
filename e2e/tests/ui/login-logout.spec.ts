import { expect, test } from "@playwright/test";
import { ADMIN_EMAIL, ADMIN_PASSWORD, STORAGE_STATE_PATH } from "./helpers";

test.describe("login and logout", () => {
  test.describe("unauthenticated", () => {
    test.use({ storageState: { cookies: [], origins: [] } });

    test("rejects wrong password with an inline error", async ({ page }) => {
      await page.goto("/login");
      await expect(
        page.getByRole("heading", { name: /sign in/i }),
      ).toBeVisible();

      await page.getByLabel("Email").fill(ADMIN_EMAIL);
      await page.getByLabel("Password").fill("not-the-real-password");
      await page.getByRole("button", { name: /sign in/i }).click();

      // Either the toast or the in-form error surface should appear.
      await expect
        .poll(async () => page.locator("body").innerText(), {
          message: "expected login failure feedback",
          timeout: 10_000,
        })
        .toMatch(/invalid|incorrect|failed|wrong/i);

      // Stay on the login page.
      expect(page.url()).toContain("/login");
    });

    test("signs in valid admin and lands on the dashboard", async ({
      page,
    }) => {
      await page.goto("/login");
      await page.getByLabel("Email").fill(ADMIN_EMAIL);
      await page.getByLabel("Password").fill(ADMIN_PASSWORD);
      await page.getByRole("button", { name: /sign in/i }).click();

      await page.waitForURL((url) => !url.pathname.startsWith("/login"), {
        timeout: 15_000,
      });
      // The dashboard shell renders the sidebar navigation.
      await expect(page.getByRole("link", { name: /collections/i }).first())
        .toBeVisible();
    });

    test("visiting an admin route while signed out redirects to /login", async ({
      page,
    }) => {
      await page.goto("/collections");
      await page.waitForURL((url) => url.pathname === "/login", {
        timeout: 10_000,
      });
    });
  });

  test.describe("authenticated", () => {
    test.use({ storageState: STORAGE_STATE_PATH });

    test("logs out via the user menu", async ({ page }) => {
      await page.goto("/overview");
      await page.waitForLoadState("domcontentloaded");

      // Open the user menu (avatar trigger in the sidebar footer).
      const menuTrigger = page.getByRole("button", { name: ADMIN_EMAIL });
      await menuTrigger.first().click();

      await page.getByRole("menuitem", { name: /sign out/i }).click();

      await page.waitForURL((url) => url.pathname === "/login", {
        timeout: 15_000,
      });
      await expect(
        page.getByRole("heading", { name: /sign in/i }),
      ).toBeVisible();
    });
  });
});
