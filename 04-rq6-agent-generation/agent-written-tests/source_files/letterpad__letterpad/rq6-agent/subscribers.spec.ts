/**
 * Tests for the Subscribers management page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Subscribers Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/subscribers");
    // Wait for the actual "Subscribers" heading (not the skeleton placeholder).
    await page
      .getByRole("heading", { name: "Subscribers" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Subscribers page header", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Subscribers" })
    ).toBeVisible();
  });

  test("shows subscribers help text", async ({ page }) => {
    await expect(
      page.getByText(/here you will find all the users subscribed/i)
    ).toBeVisible();
  });

  test("renders subscribers page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/subscribers/);
    await expect(page.locator("body")).toBeVisible();
  });
});
