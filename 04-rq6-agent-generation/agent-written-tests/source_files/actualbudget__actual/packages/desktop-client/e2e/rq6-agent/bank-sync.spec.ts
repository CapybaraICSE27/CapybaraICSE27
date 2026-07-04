/**
 * Tests for the Bank Sync page (/bank-sync).
 */
import { test, expect } from './fixtures';

test.describe('Bank Sync page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'More' }).click();
    await page.getByRole('link', { name: 'Bank Sync' }).click();
    await page.waitForURL('**/bank-sync');
    await page.waitForLoadState('networkidle');
  });

  test('shows Bank Sync page title', async ({ budgetPage: page }) => {
    await expect(page.getByText('Bank Sync').first()).toBeVisible();
  });

  test('shows Providers section', async ({ budgetPage: page }) => {
    await expect(page.getByText('Providers').first()).toBeVisible();
  });

  test('shows Set up bank sync button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Set up bank sync' }),
    ).toBeVisible();
  });

  test('shows Account section with Link account buttons', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByRole('button', { name: 'Link account' }).first(),
    ).toBeVisible();
  });

  test('shows all known accounts in bank sync list', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByText('Bank of America').first()).toBeVisible();
    await expect(page.getByText('Ally Savings').first()).toBeVisible();
    await expect(page.getByText('Vanguard 401k').first()).toBeVisible();
  });

  test('shows message about requiring server for bank sync', async ({
    budgetPage: page,
  }) => {
    // When no server is configured, bank sync requires server connection
    await expect(
      page.getByText(/Connect to an Actual server/).first(),
    ).toBeVisible();
  });

  test('Set up bank sync button is present (disabled without server)', async ({
    budgetPage: page,
  }) => {
    // Without a server, the "Set up bank sync" button is visible but disabled
    const setUpButton = page.getByRole('button', { name: 'Set up bank sync' });
    await expect(setUpButton).toBeVisible();
    // The button is disabled when no server is configured
    await expect(setUpButton).toBeDisabled();
  });
});
