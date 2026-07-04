import { test, expect } from '@playwright/test';

test.describe('Header gear menu actions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openHeaderMenu(page: any) {
    // Settings gear is the last header__menu-item
    const gearItem = page.locator('.header__menu-item').last();
    await gearItem.click();
    // Wait for the dropdown - "Settings" item should be visible
    await expect(page.locator('.cdk-overlay-container').getByText('Settings').first()).toBeVisible({ timeout: 5000 });
  }

  test('header gear menu shows Import Window option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Import Window...')).toBeVisible();
  });

  test('header gear menu shows Import from cURL option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Import from cURL...')).toBeVisible();
  });

  test('header gear menu shows Settings option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Settings').first()).toBeVisible();
  });

  test('header gear menu shows Star on GitHub option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Star on GitHub')).toBeVisible();
  });

  test('header gear menu shows Report a bug option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Report a bug')).toBeVisible();
  });

  test('header gear menu shows Export backup data option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Export backup data...')).toBeVisible();
  });

  test('header gear menu shows Import backup data option', async ({ page }) => {
    await openHeaderMenu(page);
    await expect(page.locator('.cdk-overlay-container').getByText('Import backup data...')).toBeVisible();
  });

  test('clicking Settings from header menu opens settings dialog', async ({ page }) => {
    await openHeaderMenu(page);
    await page.locator('.cdk-overlay-container').getByText('Settings').first().click();
    await expect(page.locator('.app-dialog-title').filter({ hasText: 'Settings' })).toBeVisible({ timeout: 5000 });
  });
});
