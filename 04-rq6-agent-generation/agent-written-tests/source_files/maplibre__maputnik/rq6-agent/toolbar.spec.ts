import { test, expect } from "@playwright/test";

const BASE = "/maputnik/";

test.describe("Toolbar", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
    // Wait for the app to initialize
    await page.waitForSelector(".maputnik-toolbar", { timeout: 15000 });
  });

  test("main page loads and toolbar is visible", async ({ page }) => {
    await expect(page.locator(".maputnik-toolbar")).toBeVisible();
    // Check page title
    await expect(page).toHaveTitle(/[Mm]aputnik/);
  });

  test("toolbar has logo and version", async ({ page }) => {
    const logo = page.locator(".maputnik-toolbar-logo");
    await expect(logo).toBeVisible();
    const name = page.locator(".maputnik-toolbar-name");
    await expect(name).toBeVisible();
    await expect(name).toHaveText("maputnik");
  });

  test("toolbar has Open button", async ({ page }) => {
    const openBtn = page.locator('[data-wd-key="nav:open"]');
    await expect(openBtn).toBeVisible();
    await expect(openBtn).toContainText("Open");
  });

  test("toolbar has Save button", async ({ page }) => {
    const saveBtn = page.locator('[data-wd-key="nav:export"]');
    await expect(saveBtn).toBeVisible();
    await expect(saveBtn).toContainText("Save");
  });

  test("toolbar has Code Editor button", async ({ page }) => {
    const codeBtn = page.locator('[data-wd-key="nav:code-editor"]');
    await expect(codeBtn).toBeVisible();
    await expect(codeBtn).toContainText("Code Editor");
  });

  test("toolbar has Data Sources button", async ({ page }) => {
    const sourcesBtn = page.locator('[data-wd-key="nav:sources"]');
    await expect(sourcesBtn).toBeVisible();
    await expect(sourcesBtn).toContainText("Data Sources");
  });

  test("toolbar has Style Settings button", async ({ page }) => {
    const settingsBtn = page.locator('[data-wd-key="nav:settings"]');
    await expect(settingsBtn).toBeVisible();
    await expect(settingsBtn).toContainText("Style Settings");
  });

  test("toolbar has Global State button", async ({ page }) => {
    const globalStateBtn = page.locator('[data-wd-key="nav:global-state"]');
    await expect(globalStateBtn).toBeVisible();
    await expect(globalStateBtn).toContainText("Global State");
  });

  test("toolbar has View selector", async ({ page }) => {
    const viewSelect = page.locator('[data-wd-key="nav:inspect"]');
    await expect(viewSelect).toBeVisible();
  });

  test("toolbar has Language selector", async ({ page }) => {
    const langSelect = page.locator('[data-wd-key="nav:language"]');
    await expect(langSelect).toBeVisible();
  });

  test("toolbar has Help link", async ({ page }) => {
    const helpLink = page.locator('[data-wd-key="toolbar:link"]');
    await expect(helpLink).toBeVisible();
    await expect(helpLink).toContainText("Help");
  });

  test("view selector defaults to Map", async ({ page }) => {
    const select = page.locator('[data-wd-key="maputnik-select"]');
    await expect(select).toHaveValue("map");
  });

  test("view selector switches to Inspect", async ({ page }) => {
    const select = page.locator('[data-wd-key="maputnik-select"]');
    await select.selectOption("inspect");
    await expect(select).toHaveValue("inspect");
    // URL should now have view=inspect
    await expect(page).toHaveURL(/view=inspect/);
  });

  test("view selector switches back to Map", async ({ page }) => {
    const select = page.locator('[data-wd-key="maputnik-select"]');
    await select.selectOption("inspect");
    await select.selectOption("map");
    await expect(select).toHaveValue("map");
  });

  test("language selector has multiple languages", async ({ page }) => {
    const langSelect = page.locator('[data-wd-key="maputnik-lang-select"]');
    const options = await langSelect.locator("option").all();
    expect(options.length).toBeGreaterThan(1);
  });

  test("language selector can switch to German", async ({ page }) => {
    const langSelect = page.locator('[data-wd-key="maputnik-lang-select"]');
    await langSelect.selectOption("de");
    await expect(langSelect).toHaveValue("de");
    // Check a button text has changed
    await expect(page.locator('[data-wd-key="nav:open"]')).toContainText("Öffnen");
  });

  test("skip links are accessible", async ({ page }) => {
    const layerListSkip = page.locator('[data-wd-key="root:skip:layer-list"]');
    const layerEditorSkip = page.locator('[data-wd-key="root:skip:layer-editor"]');
    const mapViewSkip = page.locator('[data-wd-key="root:skip:map-view"]');
    await expect(layerListSkip).toBeAttached();
    await expect(layerEditorSkip).toBeAttached();
    await expect(mapViewSkip).toBeAttached();
  });

  test("map container is visible", async ({ page }) => {
    const mapContainer = page.locator('[data-wd-key="maplibre:container"]');
    await expect(mapContainer).toBeVisible();
  });
});
