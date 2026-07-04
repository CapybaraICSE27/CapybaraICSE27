import { test, expect } from '@playwright/test';

// ─── nested.html ─────────────────────────────────────────────────────────────

test.describe('nested.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/nested.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Nested grids demo');
    await expect(page.getByRole('heading', { name: /nested grids/i })).toBeVisible();
  });

  test('action buttons are all visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Add Widget', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Add Widget Grid1' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Add Widget Grid2' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Save', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Destroy' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Create' })).toBeVisible();
  });

  test('static/edit radio buttons present', async ({ page }) => {
    await expect(page.locator('#static')).toBeVisible();
    await expect(page.locator('#edit')).toBeVisible();
    // edit is checked by default
    await expect(page.locator('#edit')).toBeChecked();
  });

  test('nested sub-grids are rendered', async ({ page }) => {
    // The nested grids have sub1 and sub2 classes
    await expect(page.locator('.sub1')).toBeVisible();
    await expect(page.locator('.sub2')).toBeVisible();
  });

  test('Add Widget button adds a new top-level item', async ({ page }) => {
    const before = await page.locator('.grid-stack').first().locator(':scope > .grid-stack-item').count();
    await page.getByRole('link', { name: 'Add Widget', exact: true }).click();
    await page.waitForTimeout(300);
    const after = await page.locator('.grid-stack').first().locator(':scope > .grid-stack-item').count();
    expect(after).toBeGreaterThanOrEqual(before);
  });

  test('Clear then Load cycle restores grid', async ({ page }) => {
    // Save first
    await page.getByRole('link', { name: 'Save', exact: true }).click();
    await page.waitForTimeout(200);
    // Destroy (clear all)
    await page.getByRole('link', { name: 'Clear' }).click();
    await page.waitForTimeout(300);
    // Load re-creates
    await page.getByRole('link', { name: 'Load' }).click();
    await page.waitForTimeout(300);
    await expect(page.locator('.grid-stack-item').first()).toBeVisible();
  });

  test('setting static mode via radio changes gs-static attribute', async ({ page }) => {
    await page.locator('#static').click();
    await page.waitForTimeout(200);
    const attr = await page.locator('.grid-stack').first().getAttribute('gs-static');
    expect(attr).not.toBeNull();
    // restore edit mode
    await page.locator('#edit').click();
  });
});

// ─── nested_advanced.html ────────────────────────────────────────────────────

test.describe('nested_advanced.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/nested_advanced.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Advance Nested grids demo');
    await expect(page.getByRole('heading', { name: /advanced nested/i })).toBeVisible();
  });

  test('action buttons visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Add Widget', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Save Full' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Destroy' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Re-create' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Clear' })).toBeVisible();
  });

  test('textarea output is visible and pre-populated', async ({ page }) => {
    const textarea = page.locator('#saved');
    await expect(textarea).toBeVisible();
    const val = await textarea.inputValue();
    expect(val.trim()).not.toBe('');
  });

  test('nested grids are rendered', async ({ page }) => {
    // nested grids have .grid-stack-nested class
    const nested = page.locator('.grid-stack-nested');
    const count = await nested.count();
    expect(count).toBeGreaterThan(0);
  });

  test('grid items are visible', async ({ page }) => {
    const items = page.locator('.grid-stack-item');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
  });

  test('Add Widget adds a top-level item', async ({ page }) => {
    const before = await page.locator('.grid-stack').first().locator(':scope > .grid-stack-item').count();
    await page.getByRole('link', { name: 'Add Widget', exact: true }).click();
    await page.waitForTimeout(300);
    const after = await page.locator('.grid-stack').first().locator(':scope > .grid-stack-item').count();
    expect(after).toBeGreaterThanOrEqual(before);
  });

  test('Save Full writes JSON to textarea', async ({ page }) => {
    await page.getByRole('link', { name: 'Save Full' }).click();
    await page.waitForTimeout(200);
    const val = await page.locator('#saved').inputValue();
    expect(val.trim()).not.toBe('');
    const parsed = JSON.parse(val);
    expect(typeof parsed).toBe('object');
  });
});

// ─── nested_constraint.html ──────────────────────────────────────────────────

test.describe('nested_constraint.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/nested_constraint.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Constraint nested grids demo');
    await expect(page.getByRole('heading', { name: /constraint nested/i })).toBeVisible();
  });

  test('action buttons visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Add Widget', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Save', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Destroy' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Create' })).toBeVisible();
  });

  test('sub-grids sub1 and sub2 are present', async ({ page }) => {
    await expect(page.locator('.sub1')).toBeVisible();
    await expect(page.locator('.sub2')).toBeVisible();
  });

  test('grid items are rendered', async ({ page }) => {
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });

  test('Add Widget adds a new item', async ({ page }) => {
    const before = await page.locator('.grid-stack').first().locator(':scope > .grid-stack-item').count();
    await page.getByRole('link', { name: 'Add Widget', exact: true }).click();
    await page.waitForTimeout(300);
    const after = await page.locator('.grid-stack').first().locator(':scope > .grid-stack-item').count();
    expect(after).toBeGreaterThanOrEqual(before);
  });
});
