import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Modal - Open Style", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("Open modal opens via toolbar button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
  });

  test("Open modal has title 'Open Style'", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Open Style");
  });

  test("Open modal has dropzone for file upload", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    const dropzone = page.locator('[data-wd-key="modal:open.dropzone"]');
    await expect(dropzone).toBeVisible();
    await expect(dropzone).toContainText("Drag and drop");
  });

  test("Open modal has URL input", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    const urlInput = page.locator('[data-wd-key="modal:open.url.input"]');
    await expect(urlInput).toBeVisible();
  });

  test("Load from URL button is disabled when URL is empty", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    const loadBtn = page.locator('[data-wd-key="modal:open.url.button"]');
    await expect(loadBtn).toBeVisible();
    await expect(loadBtn).toBeDisabled();
  });

  test("Load from URL button is enabled when URL is entered", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    const urlInput = page.locator('[data-wd-key="modal:open.url.input"]');
    await urlInput.fill("https://example.com/style.json");
    const loadBtn = page.locator('[data-wd-key="modal:open.url.button"]');
    await expect(loadBtn).toBeEnabled();
  });

  test("Open modal has gallery styles section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Gallery Styles");
    // Should show public styles
    const styleButtons = modal.locator(".maputnik-public-style-button");
    await expect(styleButtons.first()).toBeVisible();
  });

  test("Open modal closes via Escape", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("Open modal loads from URL and shows error on failure", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    const urlInput = page.locator('[data-wd-key="modal:open.url.input"]');
    await urlInput.fill("http://invalid-host-that-does-not-exist.example.com/style.json");
    const loadBtn = page.locator('[data-wd-key="modal:open.url.button"]');
    await loadBtn.click();
    // Eventually should show error (since URL won't load)
    const errorMsg = page.locator(".maputnik-modal-error");
    await expect(errorMsg).toBeVisible({ timeout: 10000 });
  });

  test("Open modal shows section for loading from URL", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Load from URL");
  });

  test("Open modal shows local style section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:open"]').click();
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Open local Style");
  });

  test("keyboard shortcut 'o' opens Open modal", async ({ page }) => {
    // Focus on body
    await page.locator("body").press("o");
    const modal = page.getByRole("dialog", { name: "Open Style" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });
});
