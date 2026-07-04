import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Modal - Style Settings", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("Settings modal opens via toolbar Style Settings button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
  });

  test("Settings modal has title 'Style Settings'", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Style Settings");
  });

  test("Settings modal has Name field", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    const nameField = modal.locator('[data-wd-key="modal:settings.name"]');
    await expect(nameField).toBeVisible();
  });

  test("Settings modal has Owner field", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    const ownerField = modal.locator('[data-wd-key="modal:settings.owner"]');
    await expect(ownerField).toBeVisible();
  });

  test("Settings modal has Glyphs URL field", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    const glyphsField = modal.locator('[data-wd-key="modal:settings.glyphs"]');
    await expect(glyphsField).toBeVisible();
  });

  test("Settings modal has renderer selector (MapLibreGL JS / OpenLayers)", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    const rendererField = modal.locator('[data-wd-key="modal:settings.maputnik:renderer"]');
    await expect(rendererField).toBeVisible();
  });

  test("Settings modal renderer defaults to MapLibreGL JS", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    // data-wd-key is directly on the <select> element (InputSelect puts it there)
    const rendererSelect = modal.locator('[data-wd-key="modal:settings.maputnik:renderer"]');
    await expect(rendererSelect).toHaveValue("mlgljs");
  });

  test("Settings modal has Projection selector", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    const projectionField = modal.locator('[data-wd-key="modal:settings.projection"]');
    await expect(projectionField).toBeVisible();
  });

  test("Settings modal Name field can be edited", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    // data-wd-key is directly on the <input> element (InputString puts it there)
    const nameInput = modal.locator('[data-wd-key="modal:settings.name"]');
    await nameInput.clear();
    await nameInput.fill("My Test Style");
    await expect(nameInput).toHaveValue("My Test Style");
  });

  test("Settings modal closes via Escape", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("keyboard shortcut 's' opens Settings modal", async ({ page }) => {
    await page.locator("body").press("s");
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test("Settings modal has Zoom field", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Zoom");
  });

  test("Settings modal has Light Color field", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Light color");
  });

  test("Settings modal can switch renderer to OpenLayers", async ({ page }) => {
    await page.locator('[data-wd-key="nav:settings"]').click();
    const modal = page.getByRole("dialog", { name: "Style Settings" });
    await expect(modal).toBeVisible();
    const rendererSelect = modal.locator('[data-wd-key="modal:settings.maputnik:renderer"]');
    await rendererSelect.selectOption("ol");
    await expect(rendererSelect).toHaveValue("ol");
  });
});
