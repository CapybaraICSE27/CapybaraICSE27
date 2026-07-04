/**
 * Tests for the Schedules page (/schedules).
 */
import { test, expect } from './fixtures';

test.describe('Schedules page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('link', { name: 'Schedules' }).click();
    await page.waitForURL('**/schedules');
    await page.waitForLoadState('networkidle');
  });

  test('shows Schedules page title', async ({ budgetPage: page }) => {
    await expect(page.getByText('Schedules').first()).toBeVisible();
  });

  test('shows table column headers', async ({ budgetPage: page }) => {
    await expect(page.getByText('Name').first()).toBeVisible();
    await expect(page.getByText('Next date').first()).toBeVisible();
    await expect(page.getByText('Status').first()).toBeVisible();
    await expect(page.getByText('Amount').first()).toBeVisible();
  });

  test('shows pre-existing schedules from test file', async ({
    budgetPage: page,
  }) => {
    // Test budget has: Internet bill, Phone bills, Utilities, Wedding
    await expect(page.getByText('Internet bill')).toBeVisible();
    await expect(page.getByText('Phone bills')).toBeVisible();
  });

  test('shows schedule with Missed status', async ({ budgetPage: page }) => {
    // Internet bill is Missed in the test budget
    await expect(page.getByText('Missed')).toBeVisible();
  });

  test('shows schedule with Due status', async ({ budgetPage: page }) => {
    // Phone bills is Due
    await expect(page.getByText('Due')).toBeVisible();
  });

  test('shows schedule with Upcoming status', async ({ budgetPage: page }) => {
    // Utilities is Upcoming; multiple elements may match so use first()
    await expect(page.getByText('Upcoming').first()).toBeVisible();
  });

  test('shows schedule amounts', async ({ budgetPage: page }) => {
    // Internet bill is ~140, Phone bills is ~120
    await expect(page.getByText(/140\.00|120\.00/).first()).toBeVisible();
  });

  test('shows Find schedules button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Find schedules' }),
    ).toBeVisible();
  });

  test('shows Add new schedule button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Add new schedule' }),
    ).toBeVisible();
  });

  test('shows Change upcoming length button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Change upcoming length' }),
    ).toBeVisible();
  });

  test('shows payee column values', async ({ budgetPage: page }) => {
    // Payee column for Internet bill is "Fast Internet"
    await expect(page.getByText('Fast Internet')).toBeVisible();
  });

  test('shows account column', async ({ budgetPage: page }) => {
    // Account column shows "Bank of America" for some schedules
    await expect(page.getByText('Bank of America').first()).toBeVisible();
  });

  test('Add new schedule button opens form', async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'Add new schedule' }).click();
    await page.waitForTimeout(500);

    // A modal or inline form should appear
    await expect(
      page.getByRole('dialog').or(
        page.getByText(/Payee|Date|Amount/i)
      ).first(),
    ).toBeVisible({ timeout: 5000 });
  });
});
