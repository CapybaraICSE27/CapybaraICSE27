import { test, expect } from '@playwright/test';

test.describe('Request Extensions dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openRequestExtensionsDialog(page: any) {
    await page.locator('[track-id="request_extensions"]').click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Request Extensions' })).toBeVisible({ timeout: 5000 });
  }

  test('opens Request Extensions dialog from side menu', async ({ page }) => {
    await openRequestExtensionsDialog(page);
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Request Extensions' })).toBeVisible();
  });

  test('Request Extensions dialog has a CodeMirror editor', async ({ page }) => {
    await openRequestExtensionsDialog(page);
    // Dialog content is in CDK overlay; use wrapper class without component scope
    await expect(page.locator('.request-extensions-wrapper .cm-editor')).toBeVisible({ timeout: 5000 });
  });

  test('closes Request Extensions dialog via Save button', async ({ page }) => {
    await openRequestExtensionsDialog(page);
    // app-dialog shows "Save" button (not "Done")
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Request Extensions' })).not.toBeVisible({ timeout: 5000 });
  });
});
