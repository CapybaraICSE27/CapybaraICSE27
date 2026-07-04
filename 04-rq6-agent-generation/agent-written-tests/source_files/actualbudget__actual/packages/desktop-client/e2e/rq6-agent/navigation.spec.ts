/**
 * Tests for navigation, sidebar, and global UI elements.
 */
import { test, expect } from './fixtures';

test.describe('Main navigation', () => {
  test('shows primary nav links: Budget, Reports, Schedules', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByRole('link', { name: 'Budget', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Reports', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Schedules', exact: true }),
    ).toBeVisible();
  });

  test('shows More button that expands secondary nav', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByRole('button', { name: 'More' })).toBeVisible();
  });

  test('More menu shows Payees, Rules, Bank Sync, Tags, Settings', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'More' }).click();
    await page.waitForTimeout(300);

    await expect(
      page.getByRole('link', { name: 'Payees', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Rules', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Bank Sync', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Tags', exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole('link', { name: 'Settings', exact: true }),
    ).toBeVisible();
  });

  test('clicking Budget link navigates to /budget', async ({
    budgetPage: page,
  }) => {
    // Navigate away first
    await page.getByRole('link', { name: 'Schedules' }).click();
    await page.waitForURL('**/schedules');

    // Then go back to budget
    await page.getByRole('link', { name: 'Budget', exact: true }).click();
    await page.waitForURL('**/budget');
    await expect(page.getByTestId('budget-table')).toBeVisible({
      timeout: 10_000,
    });
  });

  test('clicking Reports link navigates to /reports', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('link', { name: 'Reports' }).click();
    await page.waitForURL('**/reports/**');
    await expect(page.url()).toMatch(/\/reports\//);
  });

  test('clicking Schedules link navigates to /schedules', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('link', { name: 'Schedules' }).click();
    await page.waitForURL('**/schedules');
    await expect(page.getByText('Schedules').first()).toBeVisible();
  });
});

test.describe('Help menu', () => {
  test('shows Help button', async ({ budgetPage: page }) => {
    await expect(page.getByRole('button', { name: 'Help' })).toBeVisible();
  });

  test('Help menu shows Documentation link', async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'Help' }).click();
    await page.waitForTimeout(300);

    await expect(
      page.getByRole('link', { name: 'Documentation' }).or(
        page.getByText('Documentation')
      ).first(),
    ).toBeVisible();
  });

  test('Help menu shows Community support link', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Help' }).click();
    await page.waitForTimeout(300);

    await expect(
      page.getByText(/Community support/i).first(),
    ).toBeVisible();
  });

  test('Help menu shows Keyboard shortcuts option', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Help' }).click();
    await page.waitForTimeout(300);

    await expect(
      page.getByText(/Keyboard shortcuts/i).first(),
    ).toBeVisible();
  });
});

test.describe('No server indicator', () => {
  test('shows No server button/label in sidebar', async ({
    budgetPage: page,
  }) => {
    await expect(
      page.getByRole('button', { name: 'No server' }).or(
        page.getByText('No server')
      ).first(),
    ).toBeVisible();
  });
});
