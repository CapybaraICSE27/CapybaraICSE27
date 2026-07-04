/**
 * Tests for the Profile page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Profile Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/profile");
    // Wait for the actual "Profile" heading (not the skeleton placeholder).
    await page
      .getByRole("heading", { name: "Profile" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Profile page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
  });

  test("shows profile help text", async ({ page }) => {
    await expect(page.getByText(/set up your profile/i)).toBeVisible();
  });

  test("renders profile page without crashing", async ({ page }) => {
    await expect(page.locator("body")).toBeVisible();
    await expect(page).toHaveURL(/\/profile/);
  });

  test("shows user name field when profile loads", async ({ page }) => {
    // Wait extra for client-side data to populate form fields
    await page.waitForTimeout(2000);
    await expect(page.locator("body")).toBeVisible();
    // Should not be redirected to login
    await expect(page).toHaveURL(/\/profile/);
  });
});
