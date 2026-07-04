import { test, expect } from '@playwright/test';

test.describe('Settings dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openSettings(page: any) {
    // Settings gear is the last header__menu-item (the gear icon dropdown)
    const gearItem = page.locator('.header__menu-item').last();
    await gearItem.click();
    // Wait for dropdown to appear in CDK overlay
    const settingsOption = page.locator('.cdk-overlay-container').getByText('Settings').first();
    await expect(settingsOption).toBeVisible({ timeout: 5000 });
    await settingsOption.click();
    // Wait for settings dialog to appear
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Settings' })).toBeVisible({ timeout: 5000 });
  }

  test('opens Settings dialog from header gear menu', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Settings' })).toBeVisible();
  });

  test('Settings dialog shows Toggle advanced mode link', async ({ page }) => {
    await openSettings(page);
    await expect(page.getByText('Toggle advanced mode')).toBeVisible({ timeout: 5000 });
  });

  test('Settings dialog shows Keyboard Shortcuts section', async ({ page }) => {
    await openSettings(page);
    await expect(page.getByText('Keyboard Shortcuts')).toBeVisible({ timeout: 5000 });
  });

  test('Settings dialog has Save button', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator('[track-id="save_settings"]')).toBeVisible({ timeout: 5000 });
  });

  test('Settings dialog has Reset application data link', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator('[track-id="reset_application_data"]')).toBeVisible({ timeout: 5000 });
  });

  test('can toggle to advanced mode (JSON editor)', async ({ page }) => {
    await openSettings(page);
    await page.getByText('Toggle advanced mode').click();
    // After toggling, a CodeMirror editor should appear (advanced JSON mode)
    await expect(page.locator('.settings-editor-textarea .cm-editor')).toBeVisible({ timeout: 5000 });
  });

  test('can toggle back from advanced mode to form mode', async ({ page }) => {
    await openSettings(page);
    // Go to advanced mode
    await page.getByText('Toggle advanced mode').click();
    await expect(page.locator('.settings-editor-textarea .cm-editor')).toBeVisible({ timeout: 5000 });
    // Toggle back
    await page.getByText('Toggle advanced mode').click();
    await expect(page.locator('.settings-editor-textarea')).not.toBeVisible({ timeout: 5000 });
    // Schema form should be visible again
    await expect(page.locator('app-schema-form')).toBeVisible({ timeout: 5000 });
  });

  test('Settings dialog has a link to settings docs', async ({ page }) => {
    await openSettings(page);
    await expect(page.getByText('Toggle advanced mode').first()).toBeVisible({ timeout: 5000 });
    // Advanced mode: toggle first
    await page.getByText('Toggle advanced mode').click();
    // Should show a link to settings options docs
    await expect(page.getByText('Click here for available settings options')).toBeVisible({ timeout: 5000 });
  });

  test('closes Settings dialog via X button', async ({ page }) => {
    await openSettings(page);
    const closeBtn = page.locator('.ant-modal-close').first();
    await closeBtn.click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Settings' })).not.toBeVisible({ timeout: 5000 });
  });
});
