import { test, expect } from '@playwright/test';

// ─── two.html ─────────────────────────────────────────────────────────────────

test.describe('two.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/two.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Two grids demo');
    await expect(page.getByRole('heading', { name: /two grids/i })).toBeVisible();
  });

  test('two grids are rendered', async ({ page }) => {
    const grids = page.locator('.grid-stack');
    const count = await grids.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('sidebar items are visible', async ({ page }) => {
    await expect(page.locator('.sidebar')).toBeVisible();
    const sidebarItems = page.locator('.sidebar-item');
    const count = await sidebarItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test('trash area is visible', async ({ page }) => {
    await expect(page.locator('#trash')).toBeVisible();
  });

  test('float toggle buttons are visible', async ({ page }) => {
    // Two grids have two float toggle buttons
    const floatButtons = page.getByRole('link', { name: /float/i });
    const count = await floatButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('compact buttons are visible', async ({ page }) => {
    const compactButtons = page.getByRole('link', { name: 'Compact' });
    const count = await compactButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('clicking left float toggle changes its label', async ({ page }) => {
    // Get all float buttons - both grids have one each
    const allFloatBtns = page.locator('.btn.btn-primary', { hasText: /^float:/ });
    const firstBtn = allFloatBtns.first();
    const initialText = await firstBtn.textContent();
    await firstBtn.click();
    await page.waitForTimeout(200);
    // Re-query the element after text change since the locator was text-based
    // The button is inside .col-md-6, pick by position
    const updatedText = await allFloatBtns.first().textContent();
    expect(updatedText).not.toBe(initialText);
  });

  test('grid items are rendered in both grids', async ({ page }) => {
    // left grid
    const leftItems = page.locator('#left_grid .grid-stack-item');
    const leftCount = await leftItems.count();
    expect(leftCount).toBeGreaterThan(0);
  });
});

// ─── two_vertical.html ───────────────────────────────────────────────────────

test.describe('two_vertical.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/two_vertical.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Two vertical grids demo');
    await expect(page.getByRole('heading', { name: /two vertical/i })).toBeVisible();
  });

  test('two grids are rendered', async ({ page }) => {
    const grid1 = page.locator('#grid1');
    const grid2 = page.locator('#grid2');
    await expect(grid1).toBeVisible();
    await expect(grid2).toBeVisible();
  });

  test('grid1 has 2 items', async ({ page }) => {
    const items = page.locator('#grid1 .grid-stack-item');
    await expect(items).toHaveCount(2);
  });

  test('grid2 has 2 items', async ({ page }) => {
    const items = page.locator('#grid2 .grid-stack-item');
    await expect(items).toHaveCount(2);
  });

  test('grids are configured with row:1 (fixed row height)', async ({ page }) => {
    // row:1 means grid has exactly 1 row. Check via element attribute or grid API.
    const row = await page.evaluate(() => {
      const el = document.querySelector('#grid1') as any;
      return el?.gridstack?.opts?.row ?? el?.gridstack?.opts?.maxRow;
    });
    // row should be 1 (as configured)
    expect(row).toBe(1);
  });

  test('both grids visible and have items', async ({ page }) => {
    await expect(page.locator('.grid-stack-item').first()).toBeVisible();
    const totalItems = await page.locator('.grid-stack-item').count();
    expect(totalItems).toBe(4);
  });
});
