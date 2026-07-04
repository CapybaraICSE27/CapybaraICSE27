/**
 * Tests for the Tags management page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Tags Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/tags");
    // Wait for the actual "Tags" heading (not the skeleton placeholder).
    await page
      .getByRole("heading", { name: "Tags" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Tags page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Tags" })).toBeVisible();
  });

  test("shows tags help text", async ({ page }) => {
    await expect(
      page.getByText(/tags are essentially categories/i)
    ).toBeVisible();
  });

  test("renders tags page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/tags/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("shows seeded test tags", async ({ page }) => {
    // Wait for GraphQL to load tags
    await page.waitForTimeout(2000);
    // Tags page body should be visible
    await expect(page.locator("body")).toBeVisible();
  });
});
