import { test, expect } from '@playwright/test';

test.describe('URL box interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  test('can type a URL into the input via CodeMirror editor', async ({ page }) => {
    // The URL input is a CodeMirror editor (contenteditable)
    const urlEditorContent = page.locator('.url-box__input .cm-content');
    await urlEditorContent.click();
    // Select all and type new URL
    await page.keyboard.press('Control+a');
    await page.keyboard.type('https://example.com/graphql');
    await expect(urlEditorContent).toContainText('https://example.com/graphql');
  });

  test('HTTP method dropdown opens and shows verb options', async ({ page }) => {
    const methodBtn = page.locator('[track-id="http_verb"]').first();
    await methodBtn.click();
    // Dropdown should appear in the CDK overlay
    // Ant Design renders menu items as li elements
    await expect(page.locator('.cdk-overlay-container').getByText('GET').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.cdk-overlay-container').getByText('POST').first()).toBeVisible();
  });

  test('can change HTTP method to GET', async ({ page }) => {
    const methodBtn = page.locator('[track-id="http_verb"]').first();
    await methodBtn.click();
    // Wait for dropdown overlay to appear
    await page.locator('.cdk-overlay-container').getByText('GET').first().click();
    await expect(methodBtn).toContainText('GET');
  });

  test('Reload Docs button is visible', async ({ page }) => {
    const reloadDocsBtn = page.locator('[track-id="reload_docs"]').first();
    await expect(reloadDocsBtn).toBeVisible();
  });

  test('Export window button is visible in URL box', async ({ page }) => {
    const exportBtn = page.locator('[track-id="export_window"]').first();
    await expect(exportBtn).toBeVisible();
  });

  test('Add to collection button is visible', async ({ page }) => {
    const addCollectionBtn = page.locator('[track-id="save_to_collection"]').first();
    await expect(addCollectionBtn).toBeVisible();
  });
});
