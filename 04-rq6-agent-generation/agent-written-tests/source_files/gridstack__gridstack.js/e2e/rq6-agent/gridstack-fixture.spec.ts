import { test, expect } from '@playwright/test';

test.describe('GridStack Fixture – drag/drop and API tests', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/e2e/fixtures/gridstack-with-height.html');
    await page.waitForFunction(() => (window as any).testReady === true);
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page loads with title and 3 grid items', async ({ page }) => {
    await expect(page).toHaveTitle('GridStack E2E Test - Drag and Drop');
    const items = page.locator('.grid-stack-item');
    await expect(items).toHaveCount(3);
    await expect(items.nth(0)).toBeVisible();
    await expect(items.nth(1)).toBeVisible();
    await expect(items.nth(2)).toBeVisible();
  });

  test('outside area is visible', async ({ page }) => {
    await expect(page.locator('#outside-area')).toBeVisible();
    await expect(page.getByText('Outside Grid Area')).toBeVisible();
  });

  test('grid items have expected IDs', async ({ page }) => {
    await expect(page.locator('#item-1')).toBeVisible();
    await expect(page.locator('#item-2')).toBeVisible();
    await expect(page.locator('#item-3')).toBeVisible();
  });

  test('gridstack instance is accessible via window.gridstack', async ({ page }) => {
    const isGrid = await page.evaluate(() => {
      return typeof (window as any).gridstack !== 'undefined' &&
             typeof (window as any).gridstack.addWidget === 'function';
    });
    expect(isGrid).toBe(true);
  });

  test('cellWidth returns positive number for 12-column grid', async ({ page }) => {
    const cellWidth = await page.evaluate(() => {
      const grid = (window as any).gridstack;
      return grid.cellWidth();
    });
    expect(cellWidth).toBeGreaterThan(0);
  });

  test('getCellHeight returns 80 (configured cellHeight)', async ({ page }) => {
    const cellHeight = await page.evaluate(() => {
      const grid = (window as any).gridstack;
      return grid.getCellHeight();
    });
    expect(cellHeight).toBe(80);
  });

  test('dragging widget outside grid does not throw errors', async ({ page }) => {
    await page.evaluate(() => (window as any).clearConsoleMessages());

    const widget = page.locator('#item-1 .grid-stack-item-content');
    const outsideArea = page.locator('#outside-area');

    const widgetBox = await widget.boundingBox();
    const outsideBox = await outsideArea.boundingBox();

    expect(widgetBox).toBeTruthy();
    expect(outsideBox).toBeTruthy();

    // drag from widget centre toward outside area
    await page.mouse.move(widgetBox!.x + widgetBox!.width / 2, widgetBox!.y + widgetBox!.height / 2);
    await page.mouse.down();
    await page.mouse.move(outsideBox!.x + outsideBox!.width / 2, outsideBox!.y + outsideBox!.height / 2, { steps: 15 });
    await page.mouse.up();

    await page.waitForTimeout(400);

    const errors = await page.evaluate(() =>
      (window as any).getConsoleMessages().filter((m: any) => m.type === 'error')
    );
    expect(errors).toHaveLength(0);

    // widget should still be in the DOM
    await expect(page.locator('#item-1')).toBeVisible();
  });

  test('getCellFromPixel returns valid column/row coordinates', async ({ page }) => {
    const result = await page.evaluate(() => {
      const grid = (window as any).gridstack;
      const el = document.querySelector('.grid-stack') as HTMLElement;
      const rect = el.getBoundingClientRect();
      // Use a pixel near the top-left of the grid, clearly in cell (0, 0)
      const pixel = {
        left: rect.x + 5,
        top: rect.y + 5,
      };
      return grid.getCellFromPixel(pixel);
    });

    // Top-left corner should be cell (0, 0)
    expect(result.x).toBe(0);
    expect(result.y).toBe(0);
  });

  test('cellHeight change is reflected via getCellHeight', async ({ page }) => {
    await page.evaluate(() => {
      (window as any).gridstack.cellHeight(120);
    });
    const newHeight = await page.evaluate(() => (window as any).gridstack.getCellHeight());
    expect(newHeight).toBe(120);
  });
});
