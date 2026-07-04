import { test, expect } from '@playwright/test';

test.describe('Index / Navigation Page', () => {
  test('loads the main index page with correct title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('shows the main heading', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Mermaid quick test/i })).toBeVisible();
  });

  test('lists diagram type links', async ({ page }) => {
    await page.goto('/');
    const links = page.getByRole('link');
    await expect(links).not.toHaveCount(0);
  });

  test('has link to Flowchart page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Flow charts', exact: true })).toBeVisible();
  });

  test('has link to Sequence page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /Sequence/i })).toBeVisible();
  });

  test('has link to Gantt page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /Gantt/i })).toBeVisible();
  });

  test('has link to development page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: /development page/i })).toBeVisible();
  });

  test('navigates to flowchart page from index link', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Flow charts', exact: true }).click();
    await expect(page).toHaveURL(/flowchart\.html/);
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('navigates to sequence page from index link', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /^Sequence$/i }).click();
    await expect(page).toHaveURL(/sequence\.html/);
  });

  test('navigates to gantt page from index link', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: /^Gantt$/i }).click();
    await expect(page).toHaveURL(/gantt\.html/);
  });

  test('contains all expected diagram type links', async ({ page }) => {
    await page.goto('/');
    const expectedLinks = [
      /Class diagrams/i,
      /Gantt/i,
      /Git/i,
      /Pie/i,
      /Mindmap/i,
      /Sankey/i,
      /Timeline/i,
    ];
    for (const pattern of expectedLinks) {
      await expect(page.getByRole('link', { name: pattern }).first()).toBeVisible();
    }
  });
});
