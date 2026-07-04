import { test, expect } from '@playwright/test';

test.describe('Environment Manager dialog', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openEnvironmentManager(page: any) {
    // The environment selector in the header shows "No environment" by default
    // Find the header__menu-item that shows environment info (second to last)
    // It contains an eye-off icon and "No environment" text
    const envItem = page.locator('.header__menu-item').filter({ hasText: 'No environment' });
    await envItem.click();
    // Wait for the environment dropdown to appear
    const envManagerLink = page.locator('.cdk-overlay-container').getByText('Environments...');
    await expect(envManagerLink).toBeVisible({ timeout: 5000 });
    await envManagerLink.click();
    // Wait for the dialog to appear
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Environments' })).toBeVisible({ timeout: 5000 });
  }

  test('shows environment selector in header with "No environment" default', async ({ page }) => {
    await expect(page.locator('.header__menu-item').filter({ hasText: 'No environment' })).toBeVisible();
  });

  test('opens Environment Manager from environment dropdown', async ({ page }) => {
    await openEnvironmentManager(page);
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Environments' })).toBeVisible();
  });

  test('Environment Manager shows "Global environment" option', async ({ page }) => {
    await openEnvironmentManager(page);
    await expect(page.locator('.environment-manager__list-item').filter({ hasText: 'Global environment' })).toBeVisible({ timeout: 5000 });
  });

  test('Environment Manager shows Sub Environments section header', async ({ page }) => {
    await openEnvironmentManager(page);
    await expect(page.locator('.environment-manager__list-title')).toBeVisible({ timeout: 5000 });
  });

  test('Environment Manager shows Add Environment button', async ({ page }) => {
    await openEnvironmentManager(page);
    await expect(page.getByRole('button', { name: 'Add Environment' })).toBeVisible({ timeout: 5000 });
  });

  test('can add a new sub-environment', async ({ page }) => {
    await openEnvironmentManager(page);
    await page.getByRole('button', { name: 'Add Environment' }).click();
    // A new environment should appear in the list
    await expect(page.locator('.environment-manager__list-inner .environment-manager__list-item').first()).toBeVisible({ timeout: 5000 });
  });

  test('Global environment is selected by default', async ({ page }) => {
    await openEnvironmentManager(page);
    const baseEnvItem = page.locator('.environment-manager__list-item').filter({ hasText: 'Global environment' });
    await expect(baseEnvItem).toHaveClass(/environment-manager__list-item--selected/, { timeout: 5000 });
  });

  test('closes Environment Manager via Save button', async ({ page }) => {
    await openEnvironmentManager(page);
    // Environment Manager has a "Save" button (track-id="save_environments")
    await page.locator('[track-id="save_environments"]').click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Environments' })).not.toBeVisible({ timeout: 5000 });
  });
});
