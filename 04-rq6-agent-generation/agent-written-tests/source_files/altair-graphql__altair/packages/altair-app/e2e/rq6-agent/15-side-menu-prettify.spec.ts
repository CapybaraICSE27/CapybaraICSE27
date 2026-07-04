import { test, expect } from '@playwright/test';

test.describe('Side menu query actions (Prettify, Compress, etc.)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  async function hoverToolsMenu(page: any) {
    // The tools menu (briefcase icon) has a submenu that appears on hover
    // It's the side-menu-item that contains a side-menu-item-submenu
    const toolsMenu = page.locator('.side-menu-item').filter({
      has: page.locator('.side-menu-item-submenu:not(.side-menu-item-submenu--bottom)')
    }).first();
    await toolsMenu.hover();
    await expect(page.locator('[track-id="prettify"]')).toBeVisible({ timeout: 5000 });
  }

  test('side menu shows Prettify option in submenu (on hover)', async ({ page }) => {
    await hoverToolsMenu(page);
    await expect(page.locator('[track-id="prettify"]')).toBeVisible();
  });

  test('side menu shows Compress option in submenu', async ({ page }) => {
    await hoverToolsMenu(page);
    await expect(page.locator('[track-id="compress_query"]')).toBeVisible({ timeout: 5000 });
  });

  test('side menu shows Copy as cURL option in submenu', async ({ page }) => {
    await hoverToolsMenu(page);
    await expect(page.locator('[track-id="copy_as_curl"]')).toBeVisible({ timeout: 5000 });
  });

  test('side menu shows Clear option in submenu', async ({ page }) => {
    await hoverToolsMenu(page);
    await expect(page.locator('[track-id="clear"]')).toBeVisible({ timeout: 5000 });
  });

  test('side menu shows Refactor Query option in submenu', async ({ page }) => {
    await hoverToolsMenu(page);
    // Refactor Query doesn't have a track-id; use aria-label instead
    await expect(page.locator('[aria-label="Refactor Query"]')).toBeVisible({ timeout: 5000 });
  });

  test('side menu shows Convert to named query option', async ({ page }) => {
    await hoverToolsMenu(page);
    await expect(page.locator('[track-id="convert_to_named_query"]')).toBeVisible({ timeout: 5000 });
  });
});
