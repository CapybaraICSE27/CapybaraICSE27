/**
 * Tests for entity and architecture diagram pages:
 * ER, ER-multiline, C4 Context, Requirements
 */
import { test, expect } from '@playwright/test';

async function waitForMermaidSvg(page: any, timeout = 30_000): Promise<void> {
  await page.locator('svg').first().waitFor({ state: 'visible', timeout });
}

// ─────────────────────────────────────────────────────────────
// ER diagram
// ─────────────────────────────────────────────────────────────
test.describe('ER diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/er.html');
  });

  test('page loads with ER diagram title', async ({ page }) => {
    await expect(page).toHaveTitle(/ER diagram/i);
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple ER diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// ER diagram - multiline variant
// ─────────────────────────────────────────────────────────────
test.describe('ER multiline diagram page', () => {
  test('page loads and renders SVG', async ({ page }) => {
    await page.goto('/er-multiline.html');
    // This page loads external CSS - just ensure at least one SVG renders
    await waitForMermaidSvg(page, 45_000);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// C4 Context diagram
// ─────────────────────────────────────────────────────────────
test.describe('C4 Context diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/c4context.html');
  });

  test('page loads with C4 title', async ({ page }) => {
    await expect(page).toHaveTitle(/C4/i);
  });

  test('has C4 context heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /C4 context/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Requirements diagram
// ─────────────────────────────────────────────────────────────
test.describe('Requirements diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/requirements.html');
  });

  test('page loads with Requirements title', async ({ page }) => {
    await expect(page).toHaveTitle(/Requirements/i);
  });

  test('has Requirements heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Requirement diagram/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});
