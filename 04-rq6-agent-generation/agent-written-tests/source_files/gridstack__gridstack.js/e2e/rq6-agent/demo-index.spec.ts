import { test, expect } from '@playwright/test';

test.describe('Demo Index Page', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/index.html');
  });

  test('has correct heading', async ({ page }) => {
    await expect(page.locator('h1').first()).toHaveText('Demos');
  });

  test('contains key demo links', async ({ page }) => {
    // Use exact names to avoid conflicts with "column size" etc.
    // Use first() for items that appear in both the main list and the old jQuery list
    const linkNames = [
      ['Cell Height', true],
      ['Column', true],
      ['Float grid', true],
      ['Grid Lines', true],
      ['Mobile touch', true],
      ['Serialization', true],
      ['Static', true],
      ['Title drag', true],
      ['Website demo 1', true],
      ['Website demo 2', true],
    ] as const;

    for (const [name] of linkNames) {
      await expect(
        page.getByRole('link', { name, exact: true }).first()
      ).toBeVisible();
    }
  });

  test('Cell Height link has correct href', async ({ page }) => {
    const link = page.getByRole('link', { name: 'Cell Height', exact: true });
    const href = await link.getAttribute('href');
    expect(href).toBe('cell-height.html');
  });

  test('Serialization link has correct href', async ({ page }) => {
    const link = page.getByRole('link', { name: 'Serialization', exact: true });
    const href = await link.getAttribute('href');
    expect(href).toBe('serialization.html');
  });

  test('Nested grids link has correct href (main list, not old jQuery)', async ({ page }) => {
    // First occurrence is the main list; second is old jQuery section
    const link = page.getByRole('link', { name: 'Nested grids', exact: true }).first();
    const href = await link.getAttribute('href');
    expect(href).toBe('nested.html');
  });

  test('demo pages load directly by URL', async ({ page }) => {
    // Verify cell-height loads correctly via direct URL
    await page.goto('/demo/cell-height.html');
    await page.waitForSelector('.grid-stack', { state: 'visible', timeout: 10000 });
    await expect(page.getByRole('heading', { name: /cell height/i })).toBeVisible();
  });

  test('contains Angular, React, Vue wrapper sections', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Angular wrapper/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /React wrapper/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Vue wrapper/i })).toBeVisible();
  });

  test('Old jQuery section present', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Old v5\.1\.1/i })).toBeVisible();
  });
});
