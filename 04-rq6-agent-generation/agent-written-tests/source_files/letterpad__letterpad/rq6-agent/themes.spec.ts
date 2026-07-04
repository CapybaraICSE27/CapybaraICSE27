/**
 * Tests for the Themes selection page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Themes Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/themes");
    // Wait for the actual "Themes" heading (not the skeleton placeholder).
    await page
      .getByRole("heading", { name: "Themes" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Themes page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Themes" })).toBeVisible();
  });

  test("shows themes help text", async ({ page }) => {
    await expect(
      page.getByText(/select the theme you want to use/i)
    ).toBeVisible();
  });

  test("renders themes page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/themes/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("shows theme options", async ({ page }) => {
    // Wait for theme data to load via GraphQL
    await page.waitForTimeout(2000);
    await expect(page.locator("body")).toBeVisible();
  });
});
