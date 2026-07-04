/**
 * Tests for the Media gallery page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Media Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/media");
    await page
      .getByRole("heading", { name: "Media" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Media page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Media" })).toBeVisible();
  });

  test("shows media help text", async ({ page }) => {
    await expect(
      page.getByText(/here you will find the collection of images/i)
    ).toBeVisible();
  });

  test("renders media page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/media/);
    await expect(page.locator("body")).toBeVisible();
  });
});
