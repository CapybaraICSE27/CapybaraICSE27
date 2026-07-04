import { test, expect } from '@playwright/test';

test.describe('Query result panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  test('shows Result tab in the result panel', async ({ page }) => {
    // The result panel tabs - use getByRole('tab') to find the "Result" tab
    await expect(page.getByRole('tab', { name: 'Result' })).toBeVisible();
  });

  test('shows Response headers tab in the result panel', async ({ page }) => {
    await expect(page.getByRole('tab', { name: 'Response headers' })).toBeVisible();
  });

  test('empty state message shows before any request', async ({ page }) => {
    await expect(page.getByText('Ezio my friend, how may I be of service?')).toBeVisible();
  });

  test('shows tips component in empty state', async ({ page }) => {
    await expect(page.locator('app-tips')).toBeAttached();
  });

  test('Result tab is active by default in result panel', async ({ page }) => {
    const resultTab = page.getByRole('tab', { name: 'Result' });
    await expect(resultTab).toHaveAttribute('aria-selected', 'true');
  });
});
