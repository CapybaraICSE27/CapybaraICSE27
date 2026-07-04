/**
 * Tests for the Budget page (/budget).
 * Uses the test-file budget which has pre-populated categories and transactions.
 */
import { test, expect } from './fixtures';

test.describe('Budget page', () => {
  test('shows budget table', async ({ budgetPage: page }) => {
    await expect(page.getByTestId('budget-table')).toBeVisible();
  });

  test('shows category group rows', async ({ budgetPage: page }) => {
    // Groups use data-testid="row" with group name text
    await expect(
      page.getByTestId('row').filter({ hasText: 'Usual Expenses' }).first(),
    ).toBeVisible();
    await expect(
      page.getByTestId('row').filter({ hasText: 'Bills' }).first(),
    ).toBeVisible();
  });

  test('shows budget categories via category-name testid', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByTestId('category-name').filter({ hasText: 'Food' }).first(),
    ).toBeVisible();
    await expect(
      page
        .getByTestId('category-name')
        .filter({ hasText: 'Restaurants' })
        .first(),
    ).toBeVisible();
    await expect(
      page
        .getByTestId('category-name')
        .filter({ hasText: 'Entertainment' })
        .first(),
    ).toBeVisible();
    await expect(
      page
        .getByTestId('category-name')
        .filter({ hasText: 'Clothing' })
        .first(),
    ).toBeVisible();
  });

  test('displays budget month summary cards', async ({ budgetPage: page }) => {
    // budget-summary testid contains "Available funds" text
    const summary = page.getByTestId('budget-summary').first();
    await expect(summary).toBeVisible();
    await expect(summary.getByText('Available funds')).toBeVisible();
    await expect(summary.getByText('Budgeted')).toBeVisible();
  });

  test('shows the currently selected month', async ({ budgetPage: page }) => {
    // selected-budget-month shows "Jan 2017"
    const selectedMonth = page.getByTestId('selected-budget-month');
    await expect(selectedMonth).toBeVisible();
    await expect(selectedMonth).toContainText('Jan');
  });

  test('shows multiple months in view', async ({ budgetPage: page }) => {
    // The test file shows December, January, February
    await expect(page.getByText('December').first()).toBeVisible();
    await expect(page.getByText('January').first()).toBeVisible();
  });

  test('shows Add group button', async ({ budgetPage: page }) => {
    await expect(page.getByRole('button', { name: 'Add group' })).toBeVisible();
  });

  test('shows budget name in sidebar', async ({ budgetPage: page }) => {
    await expect(page.getByText('Test Budget')).toBeVisible();
  });

  test('shows income category group', async ({ budgetPage: page }) => {
    await expect(
      page.getByTestId('row').filter({ hasText: 'Income' }).first(),
    ).toBeVisible();
  });

  test('shows To Budget or Overbudgeted summary', async ({
    budgetPage: page,
  }) => {
    const toBudget = page.getByText(/To Budget:|Overbudgeted:/);
    await expect(toBudget.first()).toBeVisible();
  });

  test('Add group button creates new group', async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'Add group' }).click();
    await page.waitForTimeout(500);
    // Should show an input for the new group name
    const newInput = page.getByRole('textbox').last();
    await expect(newInput).toBeVisible({ timeout: 3000 });
  });

  test('shows budget category amounts', async ({ budgetPage: page }) => {
    // Food has 400.00 budgeted in test budget
    const budgetCells = page.getByTestId('budget');
    await expect(budgetCells.first()).toBeVisible();
  });

  test('shows group subtotals', async ({ budgetPage: page }) => {
    // Group rows should show aggregated totals
    const groupBudget = page.getByTestId('budgeted').first();
    await expect(groupBudget).toBeVisible();
  });

  test('shows budget-totals header row with Category label', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByTestId('budget-totals')).toBeVisible();
    await expect(
      page.getByTestId('budget-totals').getByText('Category'),
    ).toBeVisible();
  });
});
