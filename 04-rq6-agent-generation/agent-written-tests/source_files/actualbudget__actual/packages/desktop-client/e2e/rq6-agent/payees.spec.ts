/**
 * Tests for the Payees page (/payees).
 */
import { test, expect } from './fixtures';

test.describe('Payees page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'More' }).click();
    await page.getByRole('link', { name: 'Payees' }).click();
    await page.waitForURL('**/payees');
    await page.waitForLoadState('networkidle');
  });

  test('shows Payees page title', async ({ budgetPage: page }) => {
    await expect(page.getByText('Payees').first()).toBeVisible();
  });

  test('shows payee list with known payees', async ({ budgetPage: page }) => {
    // Test budget has: Dominion Power, Fast Internet, Kroger, etc.
    await expect(page.getByText('Dominion Power')).toBeVisible();
    await expect(page.getByText('Fast Internet')).toBeVisible();
    await expect(page.getByText('Kroger')).toBeVisible();
  });

  test('shows Create rule options for payees', async ({ budgetPage: page }) => {
    // "Create rule" appears next to each payee; multiple exist so use first()
    await expect(page.getByText('Create rule').first()).toBeVisible();
  });

  test('shows Show unused payees button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: /Show \d+ unused payees/ }),
    ).toBeVisible();
  });

  test('shows "No payees selected" message initially', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByText('No payees selected')).toBeVisible();
  });

  test('shows associated rules count for payees with rules', async ({
    budgetPage: page,
  }) => {
    // Dominion Power has "1 associated rules"
    await expect(
      page.getByText(/associated rule/i).first(),
    ).toBeVisible();
  });

  test('shows Name column header', async ({ budgetPage: page }) => {
    await expect(page.getByText('Name').first()).toBeVisible();
  });

  test('shows Category learning settings link', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByRole('button', { name: 'Category learning settings' }).or(
        page.getByText('Category learning settings')
      ).first(),
    ).toBeVisible();
  });

  test('shows transfer payees', async ({ budgetPage: page }) => {
    // Transfer payees appear for each account
    await expect(
      page.getByText(/Transfer: Bank of America/).first(),
    ).toBeVisible();
  });
});
