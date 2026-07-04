/**
 * Tests for the Tags page (/tags).
 */
import { test, expect } from './fixtures';

test.describe('Tags page', () => {
  test.beforeEach(async ({ budgetPage: page }) => {
    await page.getByRole('button', { name: 'More' }).click();
    await page.getByRole('link', { name: 'Tags' }).click();
    await page.waitForURL('**/tags');
    await page.waitForLoadState('networkidle');
  });

  test('shows Tags page title', async ({ budgetPage: page }) => {
    await expect(page.getByText('Tags').first()).toBeVisible();
  });

  test('shows Tags description text', async ({ budgetPage: page }) => {
    await expect(
      page.getByText(/User defined tags with color and description/),
    ).toBeVisible();
  });

  test('shows Add New button', async ({ budgetPage: page }) => {
    await expect(
      page.getByRole('button', { name: 'Add New' }),
    ).toBeVisible();
  });

  test('shows empty state with "No Tags" when no tags exist', async ({
    budgetPage: page,
  }) => {
    // Test file starts with no tags
    await expect(page.getByText('No Tags')).toBeVisible();
  });

  test('shows table column headers', async ({ budgetPage: page }) => {
    await expect(page.getByText('Tag').first()).toBeVisible();
    await expect(page.getByText('Description').first()).toBeVisible();
  });

  test('Add New button creates a tag form with name input', async ({
    budgetPage: page,
  }) => {
    await page.getByRole('button', { name: 'Add New' }).click();
    await page.waitForTimeout(500);

    // A form row appears with a "New tag" placeholder input
    await expect(
      page.getByPlaceholder('New tag'),
    ).toBeVisible({ timeout: 5000 });
  });
});
