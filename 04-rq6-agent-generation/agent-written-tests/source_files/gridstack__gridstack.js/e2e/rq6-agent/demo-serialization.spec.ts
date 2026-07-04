import { test, expect } from '@playwright/test';

test.describe('serialization.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/serialization.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Serialization demo');
    await expect(page.getByRole('heading', { name: /serialization/i })).toBeVisible();
  });

  test('all action buttons are visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Save', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Load', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Save Full' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Load Full' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Clear' })).toBeVisible();
  });

  test('textarea is present and readonly', async ({ page }) => {
    const textarea = page.locator('#saved-data');
    await expect(textarea).toBeVisible();
    const readOnly = await textarea.getAttribute('readonly');
    expect(readOnly).not.toBeNull();
  });

  test('initial grid has 5 items', async ({ page }) => {
    await expect(page.locator('.grid-stack-item')).toHaveCount(5);
  });

  test('Save button writes JSON to textarea', async ({ page }) => {
    await page.getByRole('link', { name: 'Save', exact: true }).click();
    const value = await page.locator('#saved-data').inputValue();
    expect(value.trim()).not.toBe('');
    // should be valid JSON array
    const parsed = JSON.parse(value);
    expect(Array.isArray(parsed)).toBe(true);
  });

  test('Clear removes all grid items', async ({ page }) => {
    await page.getByRole('link', { name: 'Clear' }).click();
    await expect(page.locator('.grid-stack-item')).toHaveCount(0);
  });

  test('Load restores items after Clear', async ({ page }) => {
    await page.getByRole('link', { name: 'Clear' }).click();
    await expect(page.locator('.grid-stack-item')).toHaveCount(0);
    await page.getByRole('link', { name: 'Load', exact: true }).click();
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });

  test('Save Full writes full grid JSON to textarea', async ({ page }) => {
    await page.getByRole('link', { name: 'Save Full' }).click();
    const value = await page.locator('#saved-data').inputValue();
    expect(value.trim()).not.toBe('');
    const parsed = JSON.parse(value);
    // Full save includes grid options and children
    expect(typeof parsed).toBe('object');
  });

  test('X button removes a widget', async ({ page }) => {
    const before = await page.locator('.grid-stack-item').count();
    // Click the first X button inside grid content
    await page.locator('.grid-stack-item-content button').first().click();
    // Wait for DOM update
    await page.waitForTimeout(200);
    const after = await page.locator('.grid-stack-item').count();
    expect(after).toBeLessThan(before);
  });
});
