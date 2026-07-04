import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

async function addBackgroundLayer(page: any, layerId: string) {
  await page.locator('[data-wd-key="layer-list:add-layer"]').click();
  const modal = page.getByRole("dialog", { name: "Add Layer" });
  await expect(modal).toBeVisible();
  const layerIdInput = modal.locator('[data-wd-key="add-layer.layer-id"] input');
  await layerIdInput.fill(layerId);
  const typeSelect = modal.locator('[data-wd-key="add-layer.layer-type"] select');
  await typeSelect.selectOption("background");
  await modal.locator('[data-wd-key="add-layer"]').click();
  await expect(modal).not.toBeVisible({ timeout: 5000 });
}

test.describe("Layer Editor", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector('[data-wd-key="layer-list"]', { timeout: 15000 });
  });

  test("layer editor appears when a layer is selected", async ({ page }) => {
    await addBackgroundLayer(page, "bg-layer");

    // Click the layer to select it
    await page.locator(".maputnik-layer-list-container").getByText("bg-layer").click();

    const layerEditor = page.locator('[data-wd-key="layer-editor"]');
    await expect(layerEditor).toBeVisible({ timeout: 5000 });
  });

  test("layer editor header shows layer type and id", async ({ page }) => {
    await addBackgroundLayer(page, "bg-layer-2");
    await page.locator(".maputnik-layer-list-container").getByText("bg-layer-2").click();

    const layerEditorHeader = page.locator('[data-wd-key="layer-editor.header"]');
    await expect(layerEditorHeader).toBeVisible({ timeout: 5000 });
    await expect(layerEditorHeader).toContainText("bg-layer-2");
  });

  test("layer editor shows ID field", async ({ page }) => {
    await addBackgroundLayer(page, "my-bg");
    await page.locator(".maputnik-layer-list-container").getByText("my-bg").click();

    const layerEditor = page.locator('[data-wd-key="layer-editor"]');
    await expect(layerEditor).toBeVisible({ timeout: 5000 });
    // ID field is in the layer editor
    const idInput = layerEditor.locator('[data-wd-key="layer-editor.layer-id"] input').first();
    await expect(idInput).toBeVisible({ timeout: 5000 });
  });

  test("layer editor shows layer type field", async ({ page }) => {
    await addBackgroundLayer(page, "type-bg");
    await page.locator(".maputnik-layer-list-container").getByText("type-bg").click();

    const layerEditor = page.locator('[data-wd-key="layer-editor"]');
    await expect(layerEditor).toBeVisible({ timeout: 5000 });
    // Type field is in the layer editor header area
    await expect(layerEditor).toContainText("background");
  });

  test("layer visibility can be toggled from layer list", async ({ page }) => {
    await addBackgroundLayer(page, "visibility-bg");

    // Use the data-wd-key pattern for visibility toggle
    const visToggle = page.locator('[data-wd-key="layer-list-item:visibility-bg:toggle-visibility"]');
    await expect(visToggle).toBeVisible();
    await visToggle.click();

    // Clicking again to restore
    await visToggle.click();
  });

  test("layer can be copied from layer list item", async ({ page }) => {
    await addBackgroundLayer(page, "copy-bg");

    const listContainer = page.locator(".maputnik-layer-list-container");
    await expect(listContainer).toContainText("copy-bg");

    // Find copy button using data-wd-key pattern
    const copyBtn = page.locator('[data-wd-key="layer-list-item:copy-bg:copy"]');
    await expect(copyBtn).toBeVisible();
    await copyBtn.click();

    // Should now have the layer and its copy
    await expect(listContainer).toContainText("copy-bg-copy");
  });

  test("layer can be deleted from layer list item", async ({ page }) => {
    await addBackgroundLayer(page, "delete-bg");

    const listContainer = page.locator(".maputnik-layer-list-container");
    await expect(listContainer).toContainText("delete-bg");

    // Find delete button using data-wd-key pattern
    const deleteBtn = page.locator('[data-wd-key="layer-list-item:delete-bg:delete"]');
    await expect(deleteBtn).toBeVisible();
    await deleteBtn.click();

    // Layer should be removed
    await expect(listContainer).not.toContainText("delete-bg", { timeout: 5000 });
  });

  test("URL state updates with selected layer", async ({ page }) => {
    await addBackgroundLayer(page, "url-bg");
    await page.locator(".maputnik-layer-list-container").getByText("url-bg").click();

    // URL should contain layer parameter
    await expect(page).toHaveURL(/layer=/);
  });

  test("layer editor skip target is accessible", async ({ page }) => {
    await addBackgroundLayer(page, "skip-bg");
    await page.locator(".maputnik-layer-list-container").getByText("skip-bg").click();

    const skipTarget = page.locator('[data-wd-key="skip-target-layer-editor"]');
    await expect(skipTarget).toBeAttached();
  });
});
