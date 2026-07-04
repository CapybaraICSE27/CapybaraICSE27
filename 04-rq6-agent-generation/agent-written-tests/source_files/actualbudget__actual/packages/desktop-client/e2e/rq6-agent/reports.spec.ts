/**
 * Tests for the Reports dashboard page (/reports/:dashboardId).
 * The test file creates a dashboard with Net Worth, Cash Flow, and overview widgets.
 */
import { test, expect } from './fixtures';

test.describe('Reports page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('link', { name: 'Reports' }).click();
    await page.waitForURL('**/reports/**');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
  });

  test('navigates to reports dashboard', async ({ budgetPage: page }) => {
    await expect(page.url()).toMatch(/\/reports\//);
  });

  test('shows Reports label in sidebar or breadcrumb', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByText('Reports:').first()).toBeVisible();
  });

  test('shows dashboard name (Main)', async ({ budgetPage: page }) => {
    // The default dashboard is named "Main"
    await expect(page.getByText('Main').first()).toBeVisible();
  });

  test('shows Add new widget button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Add new widget' }).or(
        page.getByText('Add new widget')
      ).first(),
    ).toBeVisible();
  });

  test('shows Edit dashboard button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Edit dashboard' }).or(
        page.getByText('Edit dashboard')
      ).first(),
    ).toBeVisible();
  });

  test('shows Net Worth widget', async ({ budgetPage: page }) => {
    await expect(page.getByText('Net Worth').first()).toBeVisible();
  });

  test('shows Cash Flow widget', async ({ budgetPage: page }) => {
    await expect(page.getByText('Cash Flow').first()).toBeVisible();
  });

  test('shows Income total widget', async ({ budgetPage: page }) => {
    await expect(
      page.getByText('Total Income').or(page.getByText('Income')).first(),
    ).toBeVisible();
  });

  test('shows budget overview or comparison widget', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByText(/Budget Overview|Compare/i).first(),
    ).toBeVisible();
  });

  test('reports page is accessible from main navigation', async ({
    budgetPage: page,
  }) => {
    // Already on reports page, verify we can go back to budget
    await page.getByRole('link', { name: 'Budget', exact: true }).click();
    await page.waitForURL('**/budget');
    await expect(page.getByTestId('budget-table')).toBeVisible({
      timeout: 10_000,
    });
  });

  test('shows total balance amounts in widgets', async ({
    budgetPage: page,
  }) => {
    // Net Worth widget shows the total
    await expect(page.getByText('43,108.00').first()).toBeVisible();
  });
});
