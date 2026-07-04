import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Modal - Shortcuts", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("keyboard shortcut '?' opens Shortcuts modal", async ({ page }) => {
    await page.locator("body").press("?");
    const modal = page.getByRole("dialog", { name: "Shortcuts" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test("Shortcuts modal has title 'Shortcuts'", async ({ page }) => {
    await page.locator("body").press("?");
    const modal = page.getByRole("dialog", { name: "Shortcuts" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("Shortcuts");
  });

  test("Shortcuts modal lists keyboard shortcuts", async ({ page }) => {
    await page.locator("body").press("?");
    const modal = page.getByRole("dialog", { name: "Shortcuts" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    // Check that multiple shortcuts are listed
    const kbdElements = modal.locator("kbd");
    await expect(kbdElements.first()).toBeVisible();
  });

  test("Shortcuts modal has map shortcuts section", async ({ page }) => {
    await page.locator("body").press("?");
    const modal = page.getByRole("dialog", { name: "Shortcuts" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("Map");
  });

  test("Shortcuts modal closes via Escape", async ({ page }) => {
    await page.locator("body").press("?");
    const modal = page.getByRole("dialog", { name: "Shortcuts" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("Shortcuts modal contains ESC shortcut description", async ({ page }) => {
    await page.locator("body").press("?");
    const modal = page.getByRole("dialog", { name: "Shortcuts" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("ESC");
  });
});

test.describe("Modal - Debug", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("keyboard shortcut '!' opens Debug modal", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });

  test("Debug modal has title 'Debug'", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("Debug");
  });

  test("Debug modal has Options section", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("Options");
  });

  test("Debug modal has debug checkboxes for MapLibreGL", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    const checkboxes = modal.locator('input[type="checkbox"]');
    await expect(checkboxes.first()).toBeVisible();
  });

  test("Debug modal has Links section with OSM link", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await expect(modal).toContainText("Links");
    await expect(modal.locator("a", { hasText: "Open in OSM" })).toBeVisible();
  });

  test("Debug modal closes via Escape", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("Debug modal checkboxes can be toggled", async ({ page }) => {
    await page.locator("body").press("!");
    const modal = page.getByRole("dialog", { name: "Debug" });
    await expect(modal).toBeVisible({ timeout: 5000 });
    const firstCheckbox = modal.locator('input[type="checkbox"]').first();
    const initialState = await firstCheckbox.isChecked();
    await firstCheckbox.click();
    await expect(firstCheckbox).toBeChecked({ checked: !initialState });
  });
});

test.describe("Modal - Global State", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("Global State modal opens via toolbar button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();
  });

  test("Global State modal has title 'Global State Variables'", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("Global State Variables");
  });

  test("Global State modal shows empty state message when no variables", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();
    await expect(modal).toContainText("No global state variables defined");
  });

  test("Global State modal has Add Variable button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();
    const addBtn = modal.locator('[data-wd-key="global-state-add-variable"]');
    await expect(addBtn).toBeVisible();
  });

  test("can add a global state variable", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();

    // Click Add Variable
    const addBtn = modal.locator('[data-wd-key="global-state-add-variable"]');
    await addBtn.click();

    // Should now show a variable row
    const keyField = modal.locator('[data-wd-key="global-state-variable-key:0"]');
    await expect(keyField).toBeVisible();
    const valueField = modal.locator('[data-wd-key="global-state-variable-value:0"]');
    await expect(valueField).toBeVisible();
  });

  test("can remove a global state variable", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();

    // Add a variable first
    await modal.locator('[data-wd-key="global-state-add-variable"]').click();
    const keyField = modal.locator('[data-wd-key="global-state-variable-key:0"]');
    await expect(keyField).toBeVisible();

    // Remove the variable
    const removeBtn = modal.locator('[data-wd-key="global-state-remove-variable"]').first();
    await removeBtn.click();

    // Should be gone, empty state message shown
    await expect(modal).toContainText("No global state variables defined", { timeout: 5000 });
  });

  test("can add multiple global state variables", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();

    // Add two variables
    await modal.locator('[data-wd-key="global-state-add-variable"]').click();
    await modal.locator('[data-wd-key="global-state-add-variable"]').click();

    // Should show two variable rows
    const keyField0 = modal.locator('[data-wd-key="global-state-variable-key:0"]');
    const keyField1 = modal.locator('[data-wd-key="global-state-variable-key:1"]');
    await expect(keyField0).toBeVisible();
    await expect(keyField1).toBeVisible();
  });

  test("Global State modal closes via Escape", async ({ page }) => {
    await page.locator('[data-wd-key="nav:global-state"]').click();
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible({ timeout: 5000 });
  });

  test("keyboard shortcut 'g' opens Global State modal", async ({ page }) => {
    await page.locator("body").press("g");
    const modal = page.getByRole("dialog", { name: "Global State Variables" });
    await expect(modal).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Code Editor", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("Code Editor opens via toolbar button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:code-editor"]').click();
    // Code editor replaces the layer list/editor panels
    const codeEditorContainer = page.locator(".maputnik-layout-code-editor");
    await expect(codeEditorContainer).toBeVisible({ timeout: 5000 });
  });

  test("Code Editor shows close button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:code-editor"]').click();
    // The close button has aria-label="Close" which overrides visible text
    const closeBtn = page.locator(".maputnik-layout-code-editor button.maputnik-button").first();
    await expect(closeBtn).toBeVisible({ timeout: 5000 });
  });

  test("Code Editor can be closed via close button", async ({ page }) => {
    await page.locator('[data-wd-key="nav:code-editor"]').click();
    const closeBtn = page.locator(".maputnik-layout-code-editor button.maputnik-button").first();
    await expect(closeBtn).toBeVisible({ timeout: 5000 });
    await closeBtn.click();
    // Code editor container should be gone
    await expect(page.locator(".maputnik-layout-code-editor")).not.toBeVisible({ timeout: 5000 });
    // Layer list should be back
    await expect(page.locator('[data-wd-key="layer-list"]')).toBeVisible();
  });

  test("Code Editor shows JSON content", async ({ page }) => {
    await page.locator('[data-wd-key="nav:code-editor"]').click();
    const codeEditor = page.locator(".maputnik-code-editor");
    await expect(codeEditor).toBeVisible({ timeout: 5000 });
  });

  test("Code Editor hides layer list when open", async ({ page }) => {
    // Layer list should be visible initially
    await expect(page.locator('[data-wd-key="layer-list"]')).toBeVisible();

    await page.locator('[data-wd-key="nav:code-editor"]').click();

    // Layer list should be hidden when code editor is open
    await expect(page.locator('[data-wd-key="layer-list"]')).not.toBeVisible({ timeout: 5000 });
  });
});
