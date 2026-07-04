import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Modal - Data Sources", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("Sources modal opens via toolbar Data Sources button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
  });

  test("Sources modal has title 'Sources'", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Sources");
  });

  test("Sources modal has Active Sources section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Active Sources");
  });

  test("Sources modal has Choose Public Source section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Choose Public Source");
  });

  test("Sources modal has Add New Source section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Add New Source");
  });

  test("Sources modal has public source options", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    const publicSources = modal.locator(".maputnik-public-source");
    await expect(publicSources.first()).toBeVisible();
  });

  test("Sources modal has Source ID field in Add section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    const sourceIdField = modal.locator('[data-wd-key="modal:sources.add.source_id"]');
    await expect(sourceIdField).toBeVisible();
  });

  test("Sources modal has Source Type selector in Add section", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    const sourceTypeField = modal.locator('[data-wd-key="modal:sources.add.source_type"]');
    await expect(sourceTypeField).toBeVisible();
  });

  test("Sources modal Add Source button is present", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    const addBtn = modal.locator('[data-wd-key="modal:sources.add.add_source"]');
    await expect(addBtn).toBeVisible();
  });

  test("Sources modal can add a GeoJSON source", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();

    // data-wd-key is directly on the <select> element
    const sourceTypeSelect = modal.locator('[data-wd-key="modal:sources.add.source_type"]');
    await sourceTypeSelect.selectOption("geojson_json");

    // data-wd-key is directly on the <input> element
    const sourceIdInput = modal.locator('[data-wd-key="modal:sources.add.source_id"]');
    await sourceIdInput.clear();
    await sourceIdInput.fill("my-geojson-source");

    // Add the source
    const addBtn = modal.locator('[data-wd-key="modal:sources.add.add_source"]');
    await addBtn.click();

    // Source should appear in active sources
    const activeSources = modal.locator(".maputnik-active-source-type-editor");
    await expect(activeSources.first()).toBeVisible({ timeout: 5000 });
  });

  test("Sources modal closes via Escape", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("keyboard shortcut 'd' opens Sources modal", async ({ page }) => {
    await page.locator("body").press("d");
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test("added source can be deleted", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();

    // Add a source
    const sourceTypeSelect = modal.locator('[data-wd-key="modal:sources.add.source_type"]');
    await sourceTypeSelect.selectOption("geojson_json");
    const sourceIdInput = modal.locator('[data-wd-key="modal:sources.add.source_id"]');
    await sourceIdInput.clear();
    await sourceIdInput.fill("deletable-source");
    const addBtn = modal.locator('[data-wd-key="modal:sources.add.add_source"]');
    await addBtn.click();

    // Wait for it to appear
    await expect(modal.locator(".maputnik-active-source-type-editor")).toBeVisible({ timeout: 5000 });
    await expect(modal.locator(".maputnik-active-source-type-editor-header-id").filter({ hasText: "#deletable-source" })).toBeVisible();

    // Click delete button
    const deleteBtn = modal.locator("button[aria-label*='deletable-source']").first();
    await deleteBtn.click();

    // Source should be removed
    await expect(modal.locator(".maputnik-active-source-type-editor-header-id").filter({ hasText: "#deletable-source" })).not.toBeVisible({ timeout: 5000 });
  });

  test("Sources modal source type options include multiple types", async ({ page }) => {
    await page.locator('[data-wd-key="nav:sources"]').click();
    const modal = page.getByRole("dialog", { name: "Sources" });
    await expect(modal).toBeVisible();
    // data-wd-key is directly on the <select> element
    const sourceTypeSelect = modal.locator('[data-wd-key="modal:sources.add.source_type"]');
    const options = await sourceTypeSelect.locator("option").all();
    expect(options.length).toBeGreaterThan(3);
  });
});
