/**
 * Tests for specialty diagram pages:
 * Mindmap, Timeline, Journey, Architecture, Block, ZenUML
 */
import { test, expect } from '@playwright/test';

async function waitForMermaidSvg(page: any, timeout = 30_000): Promise<void> {
  await page.locator('svg').first().waitFor({ state: 'visible', timeout });
}

// ─────────────────────────────────────────────────────────────
// Mindmap
// ─────────────────────────────────────────────────────────────
test.describe('Mindmap page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/mindmap.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mindmap/i);
  });

  test('has Mindmap heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Mindmap/i }).first()).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Timeline
// ─────────────────────────────────────────────────────────────
test.describe('Timeline page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/timeline.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Journey
// ─────────────────────────────────────────────────────────────
test.describe('Journey page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/journey.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Journey heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Journey/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Architecture
// ─────────────────────────────────────────────────────────────
test.describe('Architecture page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/architecture.html');
  });

  test('page loads with Architecture title', async ({ page }) => {
    await expect(page).toHaveTitle(/Architecture/i);
  });

  test('has Architecture diagram heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Architecture/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page, 45_000);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple architecture diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 45_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// Block diagram
// ─────────────────────────────────────────────────────────────
test.describe('Block diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/block.html');
  });

  test('page loads with Block title', async ({ page }) => {
    await expect(page).toHaveTitle(/Block/i);
  });

  test('has Block diagram heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Block diagram/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// ZenUML
// ─────────────────────────────────────────────────────────────
test.describe('ZenUML page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/zenuml.html');
  });

  test('page loads with ZenUML title', async ({ page }) => {
    await expect(page).toHaveTitle(/Zenuml/i);
  });

  test('has ZenUML heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Zenuml/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page, 45_000);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple ZenUML diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 45_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});
