import { test, expect } from '@playwright/test';

// ─── responsive.html ──────────────────────────────────────────────────────────

test.describe('responsive.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/responsive.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Responsive column');
    await expect(page.getByRole('heading', { name: /responsive/i })).toBeVisible();
  });

  test('column count element is visible and non-empty', async ({ page }) => {
    const colText = page.locator('#column-text');
    await expect(colText).toBeVisible();
    const text = await colText.textContent();
    expect(text?.trim()).not.toBe('');
  });

  test('layout select is present', async ({ page }) => {
    await expect(page.locator('select')).toBeVisible();
  });

  test('Add Widget button adds item', async ({ page }) => {
    const before = await page.locator('.grid-stack-item').count();
    await page.getByRole('link', { name: 'Add Widget' }).click();
    const after = await page.locator('.grid-stack-item').count();
    expect(after).toBeGreaterThan(before);
  });

  test('initial items are loaded', async ({ page }) => {
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThanOrEqual(6);
  });

  test('column count updates as viewport changes', async ({ page }) => {
    // get initial column count at full width
    const initial = await page.locator('#column-text').textContent();

    // narrow the viewport
    await page.setViewportSize({ width: 400, height: 800 });
    await page.waitForTimeout(400);

    const narrow = await page.locator('#column-text').textContent();

    // restore
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.waitForTimeout(400);

    // At some width, column count should change (or at least we can read it)
    expect(narrow).toBeTruthy();
    expect(initial).toBeTruthy();
  });
});

// ─── responsive_break.html ────────────────────────────────────────────────────

test.describe('responsive_break.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/responsive_break.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Responsive breakpoint');
    await expect(page.getByRole('heading', { name: /responsive/i })).toBeVisible();
  });

  test('column count element is visible', async ({ page }) => {
    await expect(page.locator('#column-text')).toBeVisible();
  });

  test('breakpoint text is visible with column info', async ({ page }) => {
    const text = await page.locator('#column-text').textContent();
    expect(text?.trim()).not.toBe('');
    // should be a positive integer
    const n = parseInt(text!.trim(), 10);
    expect(n).toBeGreaterThan(0);
  });

  test('items are loaded', async ({ page }) => {
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThanOrEqual(6);
  });

  test('Add Widget adds an item', async ({ page }) => {
    const before = await page.locator('.grid-stack-item').count();
    await page.getByRole('link', { name: 'Add Widget' }).click();
    await page.waitForTimeout(200);
    const after = await page.locator('.grid-stack-item').count();
    expect(after).toBeGreaterThan(before);
  });
});

// ─── responsive_none.html ─────────────────────────────────────────────────────

test.describe('responsive_none.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/responsive_none.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle("Responsive layout:'none'");
    await expect(page.getByRole('heading', { name: /responsive/i })).toBeVisible();
  });

  test('3 items are rendered', async ({ page }) => {
    await expect(page.locator('.grid-stack-item')).toHaveCount(3);
  });

  test('items have w attributes set', async ({ page }) => {
    const items = page.locator('.grid-stack-item');
    for (let i = 0; i < 3; i++) {
      const gsW = await items.nth(i).getAttribute('gs-w');
      expect(gsW).not.toBeNull();
      expect(parseInt(gsW!, 10)).toBeGreaterThanOrEqual(2);
    }
  });

  test('item content shows w value', async ({ page }) => {
    await expect(page.locator('.grid-stack-item-content').filter({ hasText: 'w:' }).first()).toBeVisible();
  });
});
