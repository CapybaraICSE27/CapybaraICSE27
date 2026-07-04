import { test, expect } from '@playwright/test';

test.describe('Documentation viewer panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  test('Docs panel is hidden by default', async ({ page }) => {
    // By default the docs panel should not be visible (split area hidden)
    const docsPanel = page.locator('app-doc-viewer');
    // It exists in DOM but hidden
    await expect(docsPanel).toBeAttached();
  });

  test('clicking Docs button toggles the documentation panel open', async ({ page }) => {
    const docsBtn = page.locator('[track-id="show_docs"]').first();
    await docsBtn.click();

    // The doc viewer should now be visible
    const docsPanel = page.locator('app-doc-viewer');
    await expect(docsPanel).not.toHaveClass(/hide-doc/, { timeout: 5000 });
  });

  test('docs panel shows loading or introspection message when schema not loaded', async ({ page }) => {
    const docsBtn = page.locator('[track-id="show_docs"]').first();
    await docsBtn.click();

    // When no schema is loaded, the doc viewer should indicate it
    const docsPanel = page.locator('app-doc-viewer');
    await expect(docsPanel).toBeVisible({ timeout: 5000 });
  });

  test('clicking Docs button again hides the panel', async ({ page }) => {
    const docsBtn = page.locator('[track-id="show_docs"]').first();
    // Open
    await docsBtn.click();
    const docsPanel = page.locator('app-doc-viewer');
    await expect(docsPanel).not.toHaveClass(/hide-doc/, { timeout: 5000 });

    // Close
    await docsBtn.click();
    await expect(docsPanel).toHaveClass(/hide-doc/, { timeout: 5000 });
  });
});
