/**
 * Tests for the Analytics dashboard page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Analytics Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/analytics");
    await page
      .getByRole("heading", { name: /analytics/i })
      .waitFor({ timeout: 15000 });
  });

  test("renders analytics page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/analytics/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("shows Analytics heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /analytics/i })
    ).toBeVisible();
  });

  test("shows analytics help text", async ({ page }) => {
    await expect(
      page.getByText(/insights of your blog/i)
    ).toBeVisible();
  });
});
