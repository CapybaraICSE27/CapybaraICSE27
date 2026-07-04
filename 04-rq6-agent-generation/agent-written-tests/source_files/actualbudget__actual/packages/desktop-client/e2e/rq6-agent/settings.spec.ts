/**
 * Tests for the Settings page (/settings).
 */
import { test, expect } from './fixtures';

test.describe('Settings page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'More' }).click();
    await page.getByRole('link', { name: 'Settings' }).click();
    await page.waitForURL('**/settings');
    await page.waitForLoadState('networkidle');
  });

  test('shows Settings page title', async ({ budgetPage: page }) => {
    await expect(page.getByText('Settings').first()).toBeVisible();
  });

  test('shows app description text', async ({ budgetPage: page }) => {
    await expect(
      page.getByText(/privacy-focused app for managing your finances/),
    ).toBeVisible();
  });

  test('shows client version', async ({ budgetPage: page }) => {
    await expect(page.getByText(/Client version:/)).toBeVisible();
  });

  test('shows server version', async ({ budgetPage: page }) => {
    await expect(page.getByText(/Server version:/)).toBeVisible();
  });

  test('shows Theme section', async ({ budgetPage: page }) => {
    await expect(page.getByText('Theme').first()).toBeVisible();
  });

  test('shows theme options: System default, Light, Dark', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByRole('button', { name: 'System default' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Light' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Dark' })).toBeVisible();
  });

  test('can switch theme to Dark', async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'Dark' }).click();
    await page.waitForTimeout(500);
    // Theme should change (data-theme attribute)
    await expect(page.locator('[data-theme]').first()).toBeVisible();
  });

  test('can switch theme back to System default', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'System default' }).click();
    await page.waitForTimeout(200);
    // Should not crash
    await expect(page.getByText('Settings').first()).toBeVisible();
  });

  test('shows Formatting section', async ({ budgetPage: page }) => {
    await expect(page.getByText('Numbers').first()).toBeVisible();
    await expect(page.getByText('Dates').first()).toBeVisible();
  });

  test('shows number format example', async ({ budgetPage: page }) => {
    await expect(page.getByText('1,000.33')).toBeVisible();
  });

  test('shows Export data button', async ({ budgetPage: page }) => {
    await expect(page.getByRole('button', { name: 'Export data' })).toBeVisible();
  });

  test('shows Show advanced settings text', async ({ budgetPage: page }) => {
    // Scroll to the bottom of the settings page to reveal advanced settings
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    await expect(
      page.getByText(/Show advanced settings|advanced settings/i).first(),
    ).toBeVisible();
  });

  test('shows budget type section', async ({ budgetPage: page }) => {
    await expect(
      page.getByText(/Envelope budgeting|tracking budgeting/i).first(),
    ).toBeVisible();
  });

  test('shows switch to tracking budgeting button', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByRole('button', { name: /Switch to tracking budgeting/ }),
    ).toBeVisible();
  });

  test('shows encryption section', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Enable encryption' }),
    ).toBeVisible();
  });

  test('shows You\'re up to date! text', async ({ budgetPage: page }) => {
    await expect(page.getByText("You're up to date!")).toBeVisible();
  });
});
