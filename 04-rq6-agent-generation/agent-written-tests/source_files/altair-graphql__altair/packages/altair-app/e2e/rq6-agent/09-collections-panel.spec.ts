import { test, expect } from '@playwright/test';

test.describe('Collections panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function openCollectionsPanel(page: any) {
    // The collections button is in the side-menu__main-bottom section
    // Use aria-label="Collections" to specifically target the collections button
    const collectionsBtn = page.locator('[aria-label="Collections"]');
    await collectionsBtn.click();
    // Wait for the collections panel title to appear
    await expect(page.locator('.query-collections__title')).toBeVisible({ timeout: 5000 });
  }

  test('toggles Collections panel open from side menu', async ({ page }) => {
    await openCollectionsPanel(page);
    await expect(page.locator('.query-collections__title')).toBeVisible();
    await expect(page.locator('.query-collections__title')).toContainText('Collections');
  });

  test('Collections panel shows Import button', async ({ page }) => {
    await openCollectionsPanel(page);
    await expect(page.locator('[data-test-id="import-collection"]')).toBeVisible({ timeout: 5000 });
  });

  test('Collections panel shows Search button', async ({ page }) => {
    await openCollectionsPanel(page);
    await expect(page.locator('[data-test-id="search-collection"]')).toBeVisible({ timeout: 5000 });
  });

  test('Collections panel shows sort dropdown button', async ({ page }) => {
    await openCollectionsPanel(page);
    const sortBtn = page.locator('.query-collections__actions--right button');
    await expect(sortBtn).toBeVisible({ timeout: 5000 });
  });

  test('Collections panel shows empty state text', async ({ page }) => {
    await openCollectionsPanel(page);
    await expect(page.locator('.query-collections__empty, .collections-empty')).toBeVisible({ timeout: 5000 }).catch(async () => {
      // Fallback: look for the empty text specifically
      await expect(page.getByText('Your collections would appear here.')).toBeVisible({ timeout: 5000 });
    });
  });

  test('toggles Collections panel closed', async ({ page }) => {
    await openCollectionsPanel(page);
    await expect(page.locator('.query-collections__title')).toBeVisible({ timeout: 5000 });

    // Click again to close
    const collectionsBtn = page.locator('[aria-label="Collections"]');
    await collectionsBtn.click();
    await expect(page.locator('.query-collections-wrapper')).toHaveClass(/query-collections-wrapper--close/, { timeout: 5000 });
  });

  test('Search button toggles search input', async ({ page }) => {
    await openCollectionsPanel(page);
    await page.locator('[data-test-id="search-collection"]').click();
    // Search input should appear with placeholder "Search"
    await expect(page.locator('input[placeholder="Search"]')).toBeVisible({ timeout: 5000 });
  });

  test('sort dropdown opens and shows options', async ({ page }) => {
    await openCollectionsPanel(page);
    // Click the sort button
    await page.locator('.query-collections__actions--right button').click();
    // Should show sort options
    await expect(page.locator('.cdk-overlay-container').getByText('A - Z')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.cdk-overlay-container').getByText('Z - A')).toBeVisible();
    await expect(page.locator('.cdk-overlay-container').getByText('Newest')).toBeVisible();
    await expect(page.locator('.cdk-overlay-container').getByText('Oldest')).toBeVisible();
  });
});
