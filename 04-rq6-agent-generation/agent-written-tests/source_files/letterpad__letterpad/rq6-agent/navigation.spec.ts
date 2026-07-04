/**
 * Tests for navigation and layout (sidebar, header, auth redirect behavior).
 * Authentication required.
 */
import { test, expect } from "./test-fixtures";
import { AUTH_STATE_FILE } from "./helpers";

test.use({ storageState: AUTH_STATE_FILE });

test.describe("Sidebar Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/posts");
    // The loading skeleton renders a placeholder <h1> via PageSkeleton/PagePlaceholder.
    // Wait for the actual "Posts" heading (not the skeleton placeholder).
    await page
      .getByRole("heading", { name: "Posts" })
      .waitFor({ timeout: 15000 });
  });

  test("sidebar shows Posts link", async ({ page }) => {
    const postsLink = page.getByRole("link", { name: /posts/i }).first();
    await expect(postsLink).toBeVisible();
  });

  test("sidebar shows Tags link", async ({ page }) => {
    await expect(page.getByText("Tags").first()).toBeVisible();
  });

  test("sidebar shows Profile link", async ({ page }) => {
    await expect(page.getByText("Profile").first()).toBeVisible();
  });

  test("sidebar shows Settings link", async ({ page }) => {
    await expect(page.getByText("Settings").first()).toBeVisible();
  });

  test("sidebar shows Themes link", async ({ page }) => {
    await expect(page.getByText("Themes").first()).toBeVisible();
  });

  test("sidebar shows Domain Mapping link", async ({ page }) => {
    await expect(page.getByText("Domain Mapping").first()).toBeVisible();
  });

  test("sidebar shows Membership link", async ({ page }) => {
    await expect(page.getByText("Membership").first()).toBeVisible();
  });

  test("sidebar shows Analytics link", async ({ page }) => {
    await expect(page.getByText("Analytics").first()).toBeVisible();
  });

  test("sidebar shows Subscribers link", async ({ page }) => {
    await expect(page.getByText("Subscribers").first()).toBeVisible();
  });

  test("sidebar shows Logout button", async ({ page }) => {
    const logoutBtn = page.getByTestId("logout");
    await expect(logoutBtn).toBeVisible();
  });

  test("can navigate to Tags via sidebar", async ({ page }) => {
    // Use href selector to avoid ambiguous matches; waitForURL waits for actual navigation
    await page.locator('a[href="/tags"]').click();
    await page.waitForURL(/\/tags/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/tags/);
  });

  test("can navigate to Profile via sidebar", async ({ page }) => {
    await page.locator('a[href="/profile"]').click();
    await page.waitForURL(/\/profile/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/profile/);
  });

  test("can navigate to Settings via sidebar", async ({ page }) => {
    await page.locator('a[href="/settings"]').click();
    await page.waitForURL(/\/settings/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/settings/);
  });

  test("can navigate to Analytics via sidebar", async ({ page }) => {
    await page.locator('a[href="/analytics"]').click();
    await page.waitForURL(/\/analytics/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/analytics/);
  });

  test("can navigate to Themes via sidebar", async ({ page }) => {
    await page.locator('a[href="/themes"]').click();
    await page.waitForURL(/\/themes/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/themes/);
  });

  test("can navigate to Subscribers via sidebar", async ({ page }) => {
    await page.locator('a[href="/subscribers"]').click();
    await page.waitForURL(/\/subscribers/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/subscribers/);
  });

  test("can navigate to Domain Mapping via sidebar", async ({ page }) => {
    await page.locator('a[href="/domain-mapping"]').click();
    await page.waitForURL(/\/domain-mapping/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/domain-mapping/);
  });

  test("can navigate to Membership via sidebar", async ({ page }) => {
    await page.locator('a[href="/membership"]').click();
    await page.waitForURL(/\/membership/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/membership/);
  });

  test("can navigate to Media page", async ({ page }) => {
    // Navigate directly since Media may not be in sidebar
    await page.goto("/media");
    await page
      .getByRole("heading", { name: "Media" })
      .waitFor({ timeout: 15000 });
    await expect(page).toHaveURL(/\/media/);
  });
});

test.describe("Authentication Redirect", () => {
  test("authenticated user on /login gets redirected to /posts", async ({
    page,
  }) => {
    await page.goto("/login");
    // With a valid session cookie, Next.js should redirect away from /login
    await page.waitForURL(/\/posts|\/login/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/posts/);
  });
});
