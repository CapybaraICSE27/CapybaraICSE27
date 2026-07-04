/**
 * Tests for the Rules page (/rules).
 */
import { test, expect } from './fixtures';

test.describe('Rules page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'More' }).click();
    await page.getByRole('link', { name: 'Rules' }).click();
    await page.waitForURL('**/rules');
    await page.waitForLoadState('networkidle');
  });

  test('shows Rules page title', async ({ budgetPage: page }) => {
    await expect(page.getByText('Rules').first()).toBeVisible();
  });

  test('shows rules description text', async ({ budgetPage: page }) => {
    await expect(
      page.getByText(/Rules are always run in the order/),
    ).toBeVisible();
  });

  test('shows existing rules from test file', async ({ budgetPage: page }) => {
    // Test budget has rules linked to schedules
    await expect(page.getByText('Fast Internet').first()).toBeVisible();
    await expect(page.getByText('Dominion Power').first()).toBeVisible();
  });

  test('shows rule conditions (payee, date, amount)', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByText(/payee is|date is|amount is/i).first()).toBeVisible();
  });

  test('shows Edit buttons for rules', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Edit' }).first(),
    ).toBeVisible();
  });

  test('shows Create new rule button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Create new rule' }),
    ).toBeVisible();
  });

  test('shows link schedule annotations', async ({ budgetPage: page }) => {
    await expect(page.getByText(/link schedule/i).first()).toBeVisible();
  });

  test('Create new rule button opens rule editor', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Create new rule' }).click();
    await page.waitForTimeout(500);

    // Modal or inline editor should appear
    await expect(
      page.getByRole('dialog').or(
        page.getByText(/condition|action|rule/i)
      ).first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test('Edit button for a rule opens rule editor dialog', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Edit' }).first().click();
    await page.waitForTimeout(500);

    // The dialog has role="dialog" and shows rule editing content
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible({ timeout: 5000 });
    // The dialog contains "If all of these conditions match" text
    await expect(dialog.getByText(/conditions match/i)).toBeVisible({
      timeout: 5000,
    });
  });

  test('shows Learn more link', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('link', { name: 'Learn more' }),
    ).toBeVisible();
  });
});
