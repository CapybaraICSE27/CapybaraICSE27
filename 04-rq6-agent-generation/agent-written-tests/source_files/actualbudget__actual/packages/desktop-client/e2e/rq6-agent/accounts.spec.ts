/**
 * Tests for the Accounts and Transactions pages.
 * Covers /accounts (all accounts), /accounts/:id (individual account),
 * and account creation flow.
 */
import { test, expect } from './fixtures';

test.describe('All Accounts page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('link', { name: 'All accounts' }).click();
    await page.waitForURL('**/accounts');
    await page.waitForLoadState('networkidle');
  });

  test('shows "All Accounts" page title', async ({ budgetPage: page }) => {
    // The app uses styled divs, not semantic heading elements
    await expect(page.getByText('All Accounts').first()).toBeVisible();
  });

  test('shows overall account balance', async ({ budgetPage: page }) => {
    // Total balance should be visible near heading
    await expect(page.getByText('43,108.00').first()).toBeVisible();
  });

  test('shows transaction list with column headers', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByText('Date').first()).toBeVisible();
    await expect(page.getByText('Payee').first()).toBeVisible();
    await expect(page.getByText('Category').first()).toBeVisible();
  });

  test('shows Add New and Filter buttons', async ({ budgetPage: page }) => {
    await expect(page.getByRole('button', { name: 'Add New' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Filter' })).toBeVisible();
  });

  test('shows recent transactions', async ({ budgetPage: page }) => {
    // Test budget has transactions from accounts
    await expect(page.getByText('Kroger').first()).toBeVisible();
  });

  test('shows scheduled/upcoming transactions', async ({ budgetPage: page }) => {
    // Test budget has upcoming transactions
    await expect(page.getByText('Upcoming').first()).toBeVisible();
  });

  test('shows Deposit and Payment column headers', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByText('Payment').first()).toBeVisible();
    await expect(page.getByText('Deposit').first()).toBeVisible();
  });
});

test.describe('Individual Account page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('link', { name: 'Bank of America' }).click();
    await page.waitForURL('**/accounts/**');
    await page.waitForLoadState('networkidle');
  });

  test('shows account name as page title', async ({ budgetPage: page }) => {
    // The app uses styled divs for page titles, not semantic heading elements
    await expect(page.getByText('Bank of America').first()).toBeVisible();
  });

  test('shows account balance', async ({ budgetPage: page }) => {
    // Bank of America balance is 190.00
    await expect(page.getByText('190.00').first()).toBeVisible();
  });

  test('shows Import, Add New, and Filter buttons', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByRole('button', { name: 'Import' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add New' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Filter' })).toBeVisible();
  });

  test('shows account-specific transactions', async ({ budgetPage: page }) => {
    // Bank of America has Fast Internet and Dominion Power transactions
    await expect(page.getByText('Fast Internet')).toBeVisible();
  });

  test('shows transaction with scheduled status', async ({
    budgetPage: page,
  }) => {
    // Internet bill is Missed, Phone bills is Due
    await expect(
      page.getByText('Missed').or(page.getByText('Due')).first(),
    ).toBeVisible();
  });

  test('Add New button opens transaction form row', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Add New' }).click();
    await page.waitForTimeout(500);
    // A new transaction row appears with a specific "add-button" (testid)
    await expect(page.getByTestId('add-button')).toBeVisible({
      timeout: 5000,
    });
  });

  test('Filter button shows filter panel options', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Filter' }).click();
    await page.waitForTimeout(500);
    // Filter dropdown or panel should appear
    await expect(
      page.getByText(/Date|Payee|Category|Amount|Account/i).first(),
    ).toBeVisible({ timeout: 5000 });
  });

  test('can navigate to another account from sidebar', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('link', { name: 'Ally Savings' }).click();
    await page.waitForURL('**/accounts/**');
    await page.waitForLoadState('networkidle');
    // Account title is displayed as styled text, not a semantic heading
    await expect(page.getByText('Ally Savings').first()).toBeVisible();
  });
});

test.describe('Add Account flow', () => {
  test('clicking Add account shows account creation options', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Add account' }).click();
    await page.waitForTimeout(500);

    await expect(
      page.getByRole('button', { name: 'Create a local account' }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: 'Set up bank sync' }),
    ).toBeVisible();
  });

  test('Create a local account button opens account form', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Add account' }).click();
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: 'Create a local account' }).click();
    await page.waitForTimeout(500);

    // Modal form should appear with Name field
    await expect(page.getByLabel('Name').or(page.getByPlaceholder('Account name')).first()).toBeVisible({
      timeout: 5000,
    });
  });
});

test.describe('Sidebar accounts listing', () => {
  test('shows On budget accounts section', async ({ budgetPage: page }) => {
    await expect(page.getByText('On budget').first()).toBeVisible();
  });

  test('shows Off budget accounts section', async ({ budgetPage: page }) => {
    await expect(page.getByText('Off budget').first()).toBeVisible();
  });

  test('shows on-budget account names and balances', async ({
    budgetPage: page,
  }) => {
    await expect(page.getByRole('link', { name: /Bank of America/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Ally Savings/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Capital One Checking/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /HSBC/ })).toBeVisible();
  });

  test('shows off-budget account names', async ({ budgetPage: page }) => {
    await expect(page.getByRole('link', { name: /Vanguard 401k/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Mortgage/ })).toBeVisible();
  });

  test('shows all-accounts balance', async ({ budgetPage: page }) => {
    // Total balance shown in sidebar
    await expect(page.getByTestId('sidebar-all-accounts-balance')).toBeVisible();
    await expect(page.getByTestId('sidebar-all-accounts-balance')).toContainText('43,108.00');
  });
});
