/**
 * Tests for advanced/specialized diagram pages:
 * Packet, Radar, Venn, TreeView, Wardley, Treemap, Railroad,
 * Ishikawa, Dataflow, Info, Error
 */
import { test, expect } from '@playwright/test';

async function waitForMermaidSvg(page: any, timeout = 30_000): Promise<void> {
  await page.locator('svg').first().waitFor({ state: 'visible', timeout });
}

// ─────────────────────────────────────────────────────────────
// Packet diagram
// ─────────────────────────────────────────────────────────────
test.describe('Packet diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/packet.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Packet heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Packet/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Radar chart
// ─────────────────────────────────────────────────────────────
test.describe('Radar chart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/radar.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Radar heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Radar/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Venn diagram
// ─────────────────────────────────────────────────────────────
test.describe('Venn diagram page', () => {
  test('page loads and renders SVG', async ({ page }) => {
    await page.goto('/venn.html');
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// TreeView diagram
// ─────────────────────────────────────────────────────────────
test.describe('TreeView diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/treeView.html');
  });

  test('page loads with TreeView title', async ({ page }) => {
    await expect(page).toHaveTitle(/TreeView/i);
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Wardley maps
// ─────────────────────────────────────────────────────────────
test.describe('Wardley maps page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/wardley.html');
  });

  test('page loads with Wardley title', async ({ page }) => {
    await expect(page).toHaveTitle(/Wardley/i);
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Treemap
// ─────────────────────────────────────────────────────────────
test.describe('Treemap page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/treemap.html');
  });

  test('page loads with Treemap title', async ({ page }) => {
    await expect(page).toHaveTitle(/Treemap/i);
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Railroad diagram
// ─────────────────────────────────────────────────────────────
test.describe('Railroad diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/railroad.html');
  });

  test('page loads with Railroad title', async ({ page }) => {
    await expect(page).toHaveTitle(/Railroad/i);
  });

  test('has Railroad heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Railroad/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Ishikawa diagram
// ─────────────────────────────────────────────────────────────
test.describe('Ishikawa diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/ishikawa.html');
  });

  test('page loads with Ishikawa title', async ({ page }) => {
    await expect(page).toHaveTitle(/Ishikawa/i);
  });

  test('has Ishikawa heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Ishikawa/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Data flow chart
// ─────────────────────────────────────────────────────────────
test.describe('Data flow chart page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dataflowchart.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Data Flow/i);
  });

  test('has Data Flow heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Data Flow/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Info diagram
// ─────────────────────────────────────────────────────────────
test.describe('Info diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/info.html');
  });

  test('page loads with Mermaid title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid/i);
  });

  test('has Info heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Info diagram/i })).toBeVisible();
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('renders two info diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 30_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThanOrEqual(2);
  });
});

// ─────────────────────────────────────────────────────────────
// Error page (intentional parse errors)
// ─────────────────────────────────────────────────────────────
test.describe('Error / invalid diagram page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/error.html');
  });

  test('page loads with Error title', async ({ page }) => {
    await expect(page).toHaveTitle(/Error/i);
  });

  test('renders SVG for valid diagrams', async ({ page }) => {
    // The page has both valid and invalid diagrams
    // Valid ones should render to SVG
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });
});
