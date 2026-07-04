/**
 * Tests for the Membership page.
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Membership Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/membership");
    // The membership page either shows pricing or active membership info.
    // Wait for the page to settle.
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(3000);
  });

  test("renders membership page without redirect", async ({ page }) => {
    await expect(page).toHaveURL(/\/membership/);
    await expect(page.locator("body")).toBeVisible();
  });

  test("shows Membership heading", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: /membership/i })
    ).toBeVisible();
  });

  test("shows membership help text", async ({ page }) => {
    await expect(
      page.getByText(/get the most out of letterpad/i)
    ).toBeVisible();
  });

  test("shows pricing content or active membership info", async ({ page }) => {
    // The membership page shows either:
    // 1. Pricing table (for free users) - look for Free or Pro tier text
    // 2. Active membership info (for paid users)
    // Either way the body is visible and the page loaded
    const body = page.locator("body");
    await expect(body).toBeVisible();
    // Body must contain some pricing or membership content
    const hasContent = await page
      .getByText(/free|pro|membership|plan|trial/i)
      .first()
      .isVisible()
      .catch(() => false);
    expect(hasContent).toBe(true);
  });
});
