/**
 * Tests for the Domain Mapping page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Domain Mapping Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/domain-mapping");
    await page
      .getByRole("heading", { name: "Domain Mapping" })
      .waitFor({ timeout: 15000 });
  });

  test("shows Domain Mapping page header", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Domain Mapping" })
    ).toBeVisible();
  });

  test("shows domain mapping help text", async ({ page }) => {
    await expect(
      page.getByText(/connect a domain to your letterpad blog/i)
    ).toBeVisible();
  });

  test("renders domain mapping page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/domain-mapping/);
    await expect(page.locator("body")).toBeVisible();
  });
});
