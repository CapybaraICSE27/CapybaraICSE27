import { test, expect } from '@playwright/test';

test.describe('Window tabs management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  test('shows "+ Add new" button in the tab bar', async ({ page }) => {
    await expect(page.getByText('+ Add new')).toBeVisible();
  });

  test('can add a second window tab', async ({ page }) => {
    const addNewBtn = page.getByText('+ Add new');
    await addNewBtn.click();

    // After adding, there should be at least 2 tab items (excluding the "add new" item)
    const switcherItems = page.locator('.window-switcher__item');
    await expect(switcherItems).toHaveCount(3); // 2 tabs + "add new" button
  });

  test('switches between window tabs', async ({ page }) => {
    // Add a second window
    await page.getByText('+ Add new').click();
    // Click the first window-switcher item to activate it
    const items = page.locator('.window-switcher__item').filter({ hasText: /^(?!.*Add new)/ });
    const firstTab = items.first();
    await firstTab.click();
    await expect(firstTab).toHaveClass(/window-switcher__item--active/);
  });

  test('can close a tab when multiple windows exist', async ({ page }) => {
    // Add a second window first
    await page.getByText('+ Add new').click();

    // Count tabs before close (should be 2 real tabs + "add new")
    const tabItems = page.locator('.window-switcher__item').filter({ hasNot: page.locator(':has-text("+ Add new")') });
    const countBefore = await tabItems.count();

    // Close the last tab via the × button on the active (last) tab
    const closeBtn = page.locator('[track-id="close_window_tab"]').last();
    await closeBtn.click();

    // Should now have one fewer tab
    const countAfter = await tabItems.count();
    expect(countAfter).toBe(countBefore - 1);
  });

  test('context menu appears on right-click of a tab', async ({ page }) => {
    const firstTabItem = page.locator('app-window-switcher-item').first();
    await firstTabItem.click({ button: 'right' });

    // Context menu should show options
    await expect(page.getByText('Duplicate')).toBeVisible({ timeout: 5000 });
  });

  test('can duplicate a window from context menu', async ({ page }) => {
    const tabItems = page.locator('.window-switcher__item').filter({ hasNot: page.locator(':has-text("+ Add new")') });
    const countBefore = await tabItems.count();

    // Right-click the first tab
    const firstTabItem = page.locator('app-window-switcher-item').first();
    await firstTabItem.click({ button: 'right' });

    // Click Duplicate option
    await page.getByText('Duplicate').click();

    // Should now have one more tab
    const countAfter = await tabItems.count();
    expect(countAfter).toBe(countBefore + 1);
  });
});
