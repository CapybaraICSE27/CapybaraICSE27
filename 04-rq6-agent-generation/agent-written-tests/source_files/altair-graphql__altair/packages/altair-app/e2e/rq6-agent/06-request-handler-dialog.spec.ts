import { test, expect } from '@playwright/test';

test.describe('Request Handler dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openRequestHandlerDialog(page: any) {
    await page.locator('[track-id="show_request_handler_dialog"]').click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Request Handlers' })).toBeVisible({ timeout: 5000 });
  }

  test('opens Request Handlers dialog from side menu', async ({ page }) => {
    await openRequestHandlerDialog(page);
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Request Handlers' })).toBeVisible();
  });

  test('shows Default Request Handler selector', async ({ page }) => {
    await openRequestHandlerDialog(page);
    await expect(page.locator('.request-handler-params-title').filter({ hasText: 'Default Request Handler' })).toBeVisible({ timeout: 5000 });
  });

  test('shows Subscription URL input', async ({ page }) => {
    await openRequestHandlerDialog(page);
    await expect(page.locator('.request-handler-params-title').filter({ hasText: 'Subscription URL' })).toBeVisible({ timeout: 5000 });
  });

  test('shows request handler select dropdown', async ({ page }) => {
    await openRequestHandlerDialog(page);
    // The dialog content is in CDK overlay; use class selector (multiple selects exist, check first)
    await expect(page.locator('.dialog-select').first()).toBeVisible({ timeout: 5000 });
  });

  test('closes Request Handlers dialog via Save button', async ({ page }) => {
    await openRequestHandlerDialog(page);
    // app-dialog shows "Save" button (not "Done")
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Request Handlers' })).not.toBeVisible({ timeout: 5000 });
  });
});
