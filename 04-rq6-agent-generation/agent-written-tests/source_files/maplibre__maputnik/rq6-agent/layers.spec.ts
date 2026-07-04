import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Layer List", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector('[data-wd-key="layer-list"]', { timeout: 15000 });
  });

  test("layer list section is visible", async ({ page }) => {
    const layerList = page.locator('[data-wd-key="layer-list"]');
    await expect(layerList).toBeVisible();
  });

  test("layer list header is visible with Layers title", async ({ page }) => {
    const header = page.locator('[data-wd-key="layer-list.header"]');
    await expect(header).toBeVisible();
    await expect(header).toContainText("Layers");
  });

  test("Add Layer button is visible in layer list header", async ({ page }) => {
    const addBtn = page.locator('[data-wd-key="layer-list:add-layer"]');
    await expect(addBtn).toBeVisible();
    await expect(addBtn).toContainText("Add Layer");
  });

  test("Expand/Collapse button is visible in layer list header", async ({ page }) => {
    const expandBtn = page.locator('[data-wd-key="skip-target-layer-list"]');
    await expect(expandBtn).toBeVisible();
  });

  test("clicking Add Layer opens Add Layer modal", async ({ page }) => {
    const addBtn = page.locator('[data-wd-key="layer-list:add-layer"]');
    await addBtn.click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
  });

  test("Add Layer modal has layer ID field", async ({ page }) => {
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
    // Layer ID field
    const layerIdField = modal.locator('[data-wd-key="add-layer.layer-id"]');
    await expect(layerIdField).toBeVisible();
  });

  test("Add Layer modal has layer type selector", async ({ page }) => {
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
    const layerTypeField = modal.locator('[data-wd-key="add-layer.layer-type"]');
    await expect(layerTypeField).toBeVisible();
  });

  test("Add Layer modal has Add Layer submit button", async ({ page }) => {
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
    const submitBtn = modal.locator('[data-wd-key="add-layer"]');
    await expect(submitBtn).toBeVisible();
  });

  test("Add Layer modal can be closed by pressing Escape", async ({ page }) => {
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
    // Press Escape to close
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("can add a background layer", async ({ page }) => {
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();

    // Set layer ID
    const layerIdInput = modal.locator('[data-wd-key="add-layer.layer-id"] input').first();
    await layerIdInput.clear();
    await layerIdInput.fill("my-background");

    // Set type to background
    const typeSelect = modal.locator('[data-wd-key="add-layer.layer-type"] select').first();
    await typeSelect.selectOption("background");

    // Click Add Layer
    const submitBtn = modal.locator('[data-wd-key="add-layer"]');
    await submitBtn.click();

    // Modal should close
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Layer should appear in list
    const layerList = page.locator(".maputnik-layer-list-container");
    await expect(layerList).toContainText("my-background");
  });

  test("adding a layer with duplicate id shows error", async ({ page }) => {
    // First add a layer
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
    const layerIdInput = modal.locator('[data-wd-key="add-layer.layer-id"] input').first();
    await layerIdInput.clear();
    await layerIdInput.fill("bg-unique");
    const typeSelect = modal.locator('[data-wd-key="add-layer.layer-type"] select').first();
    await typeSelect.selectOption("background");
    await modal.locator('[data-wd-key="add-layer"]').click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Try to add with same id
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    await expect(modal).toBeVisible();
    const layerIdInput2 = modal.locator('[data-wd-key="add-layer.layer-id"] input').first();
    await layerIdInput2.clear();
    await layerIdInput2.fill("bg-unique");
    const typeSelect2 = modal.locator('[data-wd-key="add-layer.layer-type"] select').first();
    await typeSelect2.selectOption("background");
    await modal.locator('[data-wd-key="add-layer"]').click();

    // Should show error
    await expect(modal.locator(".maputnik-modal-error")).toBeVisible();
  });

  test("layer item is clickable and selects layer", async ({ page }) => {
    // First add a layer
    await page.locator('[data-wd-key="layer-list:add-layer"]').click();
    const modal = page.getByRole("dialog", { name: "Add Layer" });
    await expect(modal).toBeVisible();
    const layerIdInput = modal.locator('[data-wd-key="add-layer.layer-id"] input').first();
    await layerIdInput.fill("selectable-layer");
    const typeSelect = modal.locator('[data-wd-key="add-layer.layer-type"] select').first();
    await typeSelect.selectOption("background");
    await modal.locator('[data-wd-key="add-layer"]').click();
    await expect(modal).not.toBeVisible({ timeout: 5000 });

    // Find the layer in the list and click it
    const layerItem = page.locator(".maputnik-layer-list-container").getByText("selectable-layer");
    await layerItem.click();

    // Verify it's selected (the layer editor should appear)
    const layerEditor = page.locator('[data-wd-key="layer-editor"]');
    await expect(layerEditor).toBeVisible({ timeout: 5000 });
  });
});
