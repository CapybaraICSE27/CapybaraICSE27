import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Modal - Save/Export", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("Export/Save modal opens via toolbar Save button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
  });

  test("Export modal has title 'Save Style'", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Save Style");
  });

  test("Export modal has Save button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
    const saveBtn = modal.locator("button").filter({ hasText: /^Save$/ });
    await expect(saveBtn).toBeVisible();
  });

  test("Export modal has Create HTML button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
    const htmlBtn = modal.locator("button").filter({ hasText: "Create HTML" });
    await expect(htmlBtn).toBeVisible();
  });

  test("Export modal has token input fields", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
    // InputString renders inputs without explicit type="text", use class selector
    const inputs = modal.locator("input.maputnik-string");
    await expect(inputs.first()).toBeVisible();
  });

  test("Export modal closes via Escape", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("keyboard shortcut 'e' opens Export modal", async ({ page }) => {
    await page.locator("body").press("e");
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test("Export modal contains section for Save Style", async ({ page }) => {
    await page.locator('[data-wd-key="nav:export"]').click();
    const modal = page.getByRole("dialog", { name: "Save Style" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Save the JSON style to your computer");
  });
});
