/**
 * Tests for core diagram types: Flowchart, Sequence, Class, State, Gantt, Git
 */
import { test, expect } from '@playwright/test';

/** Wait for at least one rendered Mermaid SVG on the page */
async function waitForMermaidSvg(page: any, timeout = 30_000): Promise<void> {
  await page.locator('svg').first().waitFor({ state: 'visible', timeout });
}

// ─────────────────────────────────────────────────────────────
// Flowchart
// ─────────────────────────────────────────────────────────────
test.describe('Flowchart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/flowchart.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Flowchart/i);
  });

  test('renders at least one SVG diagram', async ({ page }) => {
    await waitForMermaidSvg(page);
    const svgs = page.locator('svg');
    await expect(svgs.first()).toBeVisible();
  });

  test('has main heading', async ({ page }) => {
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
  });

  test('renders multiple diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// Flowchart ELK
// ─────────────────────────────────────────────────────────────
test.describe('Flowchart ELK page', () => {
  test('page loads and renders SVG', async ({ page }) => {
    await page.goto('/flowchart-elk.html');
    await waitForMermaidSvg(page, 45_000);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('has a heading', async ({ page }) => {
    await page.goto('/flowchart-elk.html');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Flowchart expanded node shapes
// ─────────────────────────────────────────────────────────────
test.describe('Flowchart expanded node shapes page', () => {
  test('page loads and renders SVG', async ({ page }) => {
    await page.goto('/flowchart_expanded_node_shapes.html');
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Sequence diagram
// ─────────────────────────────────────────────────────────────
test.describe('Sequence diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/sequence.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Sequence diagram heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Sequence diagram/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple sequence diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// Class diagrams
// ─────────────────────────────────────────────────────────────
test.describe('Class diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/classchart.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Class diagrams/i);
  });

  test('has Class diagram heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Class diagram/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// State diagrams
// ─────────────────────────────────────────────────────────────
test.describe('State diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/state.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/States/i);
  });

  test('has State diagram heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /State diagram/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple state diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// Gantt chart
// ─────────────────────────────────────────────────────────────
test.describe('Gantt chart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/gantt.html');
  });

  test('page loads with Gantt title', async ({ page }) => {
    await expect(page).toHaveTitle(/Gantt/i);
  });

  test('has Gantt heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Gantt chart/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Git graph
// ─────────────────────────────────────────────────────────────
test.describe('Git graph page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/git.html');
  });

  test('page loads with Git title', async ({ page }) => {
    await expect(page).toHaveTitle(/Git Graphs/i);
  });

  test('has Git graph heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Git graph/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders multiple git graphs', async ({ page }) => {
    // Wait for at least 2 SVGs to appear - git.html has several diagrams
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});
