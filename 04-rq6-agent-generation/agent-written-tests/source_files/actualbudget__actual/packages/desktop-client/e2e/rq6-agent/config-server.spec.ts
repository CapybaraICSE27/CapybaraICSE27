/**
 * Tests for the Config Server / initial setup page.
 * This is the first screen shown when no budget is open and no server is configured.
 */
import { test, expect } from '@playwright/test';

test.describe('Config Server page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('shows "Where\'s the server?" heading on initial load', async ({
    page,
  }) => {
    await expect(
      page.getByRole('heading', { name: "Where's the server?" }),
    ).toBeVisible();
  });

  test('displays all action buttons', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'OK' })).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Use current domain' }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: "Don't use a server" }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Create test file' }),
    ).toBeVisible();
  });

  test('shows app and server version', async ({ page }) => {
    const versionText = page.locator('text=/App: v/');
    await expect(versionText).toBeVisible();
  });

  test('shows description text about server configuration', async ({
    page,
  }) => {
    await expect(
      page.getByText(/After running the server, specify the URL here/),
    ).toBeVisible();
  });

  test('creates test file and navigates to budget page', async ({ page }) => {
    await page.getByRole('button', { name: 'Create test file' }).click();
    await page.waitForURL('**/budget', { timeout: 30_000 });
    await page.waitForLoadState('networkidle');

    // Budget table should be visible after creating test file
    await expect(page.getByTestId('budget-table')).toBeVisible({
      timeout: 15_000,
    });
  });

  test('navigates to /config-server when visiting unknown route', async ({
    page,
  }) => {
    await page.goto('/some-unknown-page');
    await page.waitForLoadState('networkidle');

    // Should redirect to config-server
    await expect(
      page.getByRole('heading', { name: "Where's the server?" }),
    ).toBeVisible();
  });

  test('URL input field is present and accepts text', async ({ page }) => {
    // There should be a URL input for server configuration
    const urlInput = page.getByRole('textbox');
    await expect(urlInput).toBeVisible();
    await urlInput.fill('http://localhost:5006');
    await expect(urlInput).toHaveValue('http://localhost:5006');
  });
});
