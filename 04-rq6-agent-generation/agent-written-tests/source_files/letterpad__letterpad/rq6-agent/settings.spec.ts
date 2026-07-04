/**
 * Tests for the Settings page (all tabs).
 * Authentication required.
 *
 * Note: The Settings page's NavigationBuilder component uses a Tags GraphQL query
 * which has a known Prisma schema mismatch (batchTags selects non-existent fields).
 * We use the GraphQL mock fixture to prevent the resulting UnAuthorized redirect.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Settings Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/settings");
    // Wait for the actual "Settings" heading (not the skeleton placeholder).
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Settings page header", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
  });

  test("shows settings help text", async ({ page }) => {
    await expect(
      page.getByText(/here you can customize your blog/i)
    ).toBeVisible();
  });

  test("renders settings page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("loads settings page body", async ({ page }) => {
    // Wait for the settings form to render (data comes from GraphQL)
    await page.waitForTimeout(3000);
    await expect(page).toHaveURL(/\/settings/);
    await expect(page.locator("body")).toBeVisible();
  });
});

test.describe("Settings - SEO Tab", () => {
  test("loads SEO settings section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    // Wait for settings form data to populate
    await page.waitForTimeout(3000);
    // SEO section heading is rendered after data loads
    await expect(page.getByText(/seo configuration/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Settings - Appearance Tab", () => {
  test("loads appearance settings section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    await page.waitForTimeout(3000);
    await expect(page.getByText(/appearance/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Settings - Navigation Tab", () => {
  test("loads navigation settings section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    await page.waitForTimeout(3000);
    await expect(page.getByText(/navigation/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Settings - Keys Tab", () => {
  test("loads API keys settings section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    await page.waitForTimeout(3000);
    await expect(page.getByText(/keys/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Settings - Delete Account Tab", () => {
  test("loads delete account section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    await page.waitForTimeout(3000);
    await expect(page.getByText(/delete account/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Settings - Integrations Tab", () => {
  test("loads integrations settings section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    await page.waitForTimeout(3000);
    await expect(page.getByText(/integrations/i).first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Settings - Pages Tab", () => {
  test("loads pages settings section", async ({ page }) => {
    await page.goto("/settings");
    await page
      .getByRole("heading", { name: "Settings" })
      .waitFor({ timeout: 15000 });
    await page.waitForTimeout(3000);
    await expect(page.getByText(/pages/i).first()).toBeVisible({ timeout: 10000 });
  });
});
