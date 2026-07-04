import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("URL State Management", () => {
  test("initial page load redirects to /maputnik/", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/maputnik\//);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("URL contains layer parameter after page load", async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
    // After loading, URL should have layer= parameter
    await expect(page).toHaveURL(/layer=/);
  });

  test("inspect mode is reflected in URL", async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });

    const select = page.locator('[data-wd-key="maputnik-select"]');
    await select.selectOption("inspect");

    await expect(page).toHaveURL(/view=inspect/);
  });

  test("map mode removes view from URL", async ({ page }) => {
    await page.goto(BASE + "?view=inspect");
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });

    const select = page.locator('[data-wd-key="maputnik-select"]');
    await select.selectOption("map");

    // view parameter should be removed from URL
    const url = page.url();
    expect(url).not.toMatch(/view=/);
  });

  test("opening a modal is reflected in URL", async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });

    await page.locator('[data-wd-key="nav:settings"]').click();
    await expect(page).toHaveURL(/modal=settings/);
  });

  test("closing a modal removes it from URL", async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });

    await page.locator('[data-wd-key="nav:settings"]').click();
    await expect(page).toHaveURL(/modal=settings/);

    await page.keyboard.press("Escape");
    // Wait for modal to close
    await expect(page.getByRole("dialog", { name: "Style Settings" })).not.toBeVisible({ timeout: 5000 });
    // URL should no longer contain modal=settings
    const url = page.url();
    expect(url).not.toMatch(/modal=settings/);
  });

  test("URL with modal=open parameter opens Open modal on load", async ({ page }) => {
    // Navigate with modal parameter
    await page.goto(BASE + "?modal=open");
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
    // Wait briefly for the modal state to be applied from URL
    await page.waitForTimeout(500);
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });
});
