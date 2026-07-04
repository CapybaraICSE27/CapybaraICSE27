/**
 * Tests for dev / interactive pages:
 * - /dev/example.html  – interactive textarea + live preview
 * - /dev/architecture-randomize.html – architecture randomize test
 * - /eventmodeling.html – event modeling dev page (interactive textarea)
 */
import { test, expect } from '@playwright/test';

async function waitForMermaidSvg(page: any, timeout = 30_000): Promise<void> {
  await page.locator('svg').first().waitFor({ state: 'visible', timeout });
}

// ─────────────────────────────────────────────────────────────
// Dev example page (interactive)
// ─────────────────────────────────────────────────────────────
test.describe('Dev example page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dev/example.html');
  });

  test('page loads with development title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid development/i);
  });

  test('renders a default graph diagram on load', async ({ page }) => {
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('has a code textarea for input', async ({ page }) => {
    const textarea = page.locator('textarea#code');
    await expect(textarea).toBeVisible();
  });

  test('renders info diagram on the page', async ({ page }) => {
    // The page has a static `info` diagram below the textarea
    await waitForMermaidSvg(page);
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThanOrEqual(1);
  });

  test('textarea input updates the dynamic diagram', async ({ page }) => {
    await waitForMermaidSvg(page);

    // Clear any stored code and type a simple flowchart
    const textarea = page.locator('textarea#code');
    await textarea.click();
    await textarea.fill('graph LR\n  A --> B --> C');

    // The diagram div should be populated
    const dynamicDiv = page.locator('#dynamicDiagram svg');
    await dynamicDiv.waitFor({ state: 'visible', timeout: 20_000 });
    await expect(dynamicDiv).toBeVisible();
  });
});

// ─────────────────────────────────────────────────────────────
// Architecture randomize page
// ─────────────────────────────────────────────────────────────
test.describe('Architecture randomize page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dev/architecture-randomize.html');
  });

  test('page loads with Architecture randomize title', async ({ page }) => {
    await expect(page).toHaveTitle(/Architecture randomize/i);
  });

  test('renders at least one SVG', async ({ page }) => {
    await waitForMermaidSvg(page, 45_000);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('has descriptive heading about randomize behavior', async ({ page }) => {
    await expect(page.locator('h3').first()).toBeVisible();
  });

  test('renders multiple architecture diagrams', async ({ page }) => {
    await page.locator('svg').nth(1).waitFor({ state: 'visible', timeout: 45_000 });
    const svgCount = await page.locator('svg').count();
    expect(svgCount).toBeGreaterThan(1);
  });
});

// ─────────────────────────────────────────────────────────────
// Event modeling dev page
// ─────────────────────────────────────────────────────────────
test.describe('Event modeling page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/eventmodeling.html');
  });

  test('page loads with development title', async ({ page }) => {
    await expect(page).toHaveTitle(/Mermaid development/i);
  });

  test('has Event Modeling heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Event Modeling/i })).toBeVisible();
  });

  test('has a code textarea for input', async ({ page }) => {
    const textarea = page.locator('textarea#code');
    await expect(textarea).toBeVisible();
  });

  test('renders the static info diagram', async ({ page }) => {
    // The page always has a static `info` mermaid element
    await waitForMermaidSvg(page);
    await expect(page.locator('svg').first()).toBeVisible();
  });

  test('textarea input updates the dynamic diagram', async ({ page }) => {
    await waitForMermaidSvg(page);

    const textarea = page.locator('textarea#code');
    await textarea.click();
    await textarea.fill('graph TD\n  X --> Y');

    const dynamicDiv = page.locator('#dynamicDiagram svg');
    await dynamicDiv.waitFor({ state: 'visible', timeout: 20_000 });
    await expect(dynamicDiv).toBeVisible();
  });
});
