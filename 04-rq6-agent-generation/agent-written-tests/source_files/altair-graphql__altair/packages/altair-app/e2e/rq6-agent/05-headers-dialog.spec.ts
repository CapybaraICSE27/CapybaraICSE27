import { test, expect } from '@playwright/test';

test.describe('Headers dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openHeadersDialog(page: any) {
    await page.locator('[track-id="show_set_headers"]').click();
    // Wait for the dialog title to appear
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Headers' })).toBeVisible({ timeout: 5000 });
  }

  test('opens headers dialog from side menu', async ({ page }) => {
    await openHeadersDialog(page);
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Headers' })).toBeVisible();
    await expect(page.getByText('Add, edit and remove headers in your request')).toBeVisible();
  });

  test('headers dialog has "Add header" button', async ({ page }) => {
    await openHeadersDialog(page);
    await expect(page.getByRole('button', { name: 'Add header' })).toBeVisible({ timeout: 5000 });
  });

  test('can add a new header', async ({ page }) => {
    await openHeadersDialog(page);
    // Check count of header items before adding
    const headerItems = page.locator('.headers-editor__list-item');
    const countBefore = await headerItems.count();

    // Click "Add header" to add a new header row
    await page.getByRole('button', { name: 'Add header' }).click();

    // Should now have one more header item
    await expect(headerItems).toHaveCount(countBefore + 1, { timeout: 5000 });
  });

  test('shows Forbidden headers notice', async ({ page }) => {
    await openHeadersDialog(page);
    await expect(page.getByText('Forbidden headers will not work in the browser environment')).toBeVisible({ timeout: 5000 });
  });

  test('closes headers dialog via Done button', async ({ page }) => {
    await openHeadersDialog(page);
    await page.getByRole('button', { name: 'Done' }).click();
    // Dialog should disappear
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Headers' })).not.toBeVisible({ timeout: 5000 });
  });

  test('closes headers dialog via X button', async ({ page }) => {
    await openHeadersDialog(page);
    // Close via the modal's close button
    const closeBtn = page.locator('.ant-modal-close').first();
    await closeBtn.click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Headers' })).not.toBeVisible({ timeout: 5000 });
  });
});
