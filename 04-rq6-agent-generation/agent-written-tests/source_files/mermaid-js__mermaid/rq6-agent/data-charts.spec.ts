/**
 * Tests for data chart pages: Pie, Sankey, Quadrant, XY Charts
 */
import { test, expect } from '@playwright/test';

async function waitForMermaidSvg(page: any, timeout = 30_000): Promise<void> {
  await page.locator('svg').first().waitFor({ state: 'visible', timeout });
}

// ─────────────────────────────────────────────────────────────
// Pie chart
// ─────────────────────────────────────────────────────────────
test.describe('Pie chart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pie.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Pie chart heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Pie chart/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple pie chart diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// Sankey diagram
// ─────────────────────────────────────────────────────────────
test.describe('Sankey diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/sankey.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Sankey/i);
  });

  test('has Sankey heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Sankey/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Quadrant chart
// ─────────────────────────────────────────────────────────────
test.describe('Quadrant chart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/quadrantchart.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Quadrant chart heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Quadrant chart/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple quadrant diagrams', async ({ page }) => {
    await waitForMermaidSvg(page);
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// XY chart
// ─────────────────────────────────────────────────────────────
test.describe('XY chart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/xychart.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has XY Charts heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /XY Charts/i }).first()).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple XY charts', async ({ page }) => {
    await waitForMermaidSvg(page);
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});
