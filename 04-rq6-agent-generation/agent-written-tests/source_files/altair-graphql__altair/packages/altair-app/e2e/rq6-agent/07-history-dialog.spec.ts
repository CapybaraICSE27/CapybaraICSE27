import { test, expect } from '@playwright/test';

test.describe('History dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openHistoryDialog(page: any) {
    await page.locator('[track-id="show_history"]').click();
    // Wait for dialog to appear using dialog title
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'History' })).toBeVisible({ timeout: 5000 });
  }

  test('opens History dialog from side menu', async ({ page }) => {
    await openHistoryDialog(page);
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'History' })).toBeVisible();
  });

  test('shows Clear History button', async ({ page }) => {
    await openHistoryDialog(page);
    await expect(page.locator('[track-id="clear_history_items"]')).toBeVisible({ timeout: 5000 });
  });

  test('shows Done button in history dialog', async ({ page }) => {
    await openHistoryDialog(page);
    await expect(page.locator('[track-id="close_history_dialog"]')).toBeVisible({ timeout: 5000 });
  });

  test('closes History dialog via Done button', async ({ page }) => {
    await openHistoryDialog(page);
    await page.locator('[track-id="close_history_dialog"]').click();
    // Dialog should close
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'History' })).not.toBeVisible({ timeout: 5000 });
  });

  test('can click Clear History button without error', async ({ page }) => {
    await openHistoryDialog(page);
    await page.locator('[track-id="clear_history_items"]').click();
    // Dialog should still be visible after clearing
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'History' })).toBeVisible({ timeout: 5000 });
  });

  test('closes history dialog via X button', async ({ page }) => {
    await openHistoryDialog(page);
    const closeBtn = page.locator('.ant-modal-close').first();
    await closeBtn.click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'History' })).not.toBeVisible({ timeout: 5000 });
  });
});
