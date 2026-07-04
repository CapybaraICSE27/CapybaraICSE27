import { test, expect } from '@playwright/test';

// ─── sizeToContent.html ───────────────────────────────────────────────────────

test.describe('sizeToContent.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/sizeToContent.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('sizeToContent demo');
    await expect(page.getByRole('heading', { name: /sizeToContent/i })).toBeVisible();
  });

  test('both grid containers are rendered', async ({ page }) => {
    await expect(page.locator('#grid1')).toBeVisible();
    await expect(page.locator('#grid2')).toBeVisible();
  });

  test('action buttons are visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'clear' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'load' })).toBeVisible();
    await expect(page.getByRole('link', { name: '8' })).toBeVisible();
    await expect(page.getByRole('link', { name: '12' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Add' })).toBeVisible();
  });

  test('clear removes items from grid1', async ({ page }) => {
    await page.getByRole('link', { name: 'clear' }).click();
    await page.waitForTimeout(200);
    const count = await page.locator('#grid1 .grid-stack-item').count();
    expect(count).toBe(0);
  });

  test('load restores items after clear', async ({ page }) => {
    await page.getByRole('link', { name: 'clear' }).click();
    await page.waitForTimeout(200);
    await page.getByRole('link', { name: 'load' }).click();
    await page.waitForTimeout(300);
    const count = await page.locator('#grid1 .grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });

  test('column 8 button changes grid1 column count', async ({ page }) => {
    await page.getByRole('link', { name: '8' }).click();
    await page.waitForTimeout(200);
    const cols = await page.evaluate(() => {
      // sizeToContent.html exposes grid as window.grid (it's var in module scope but let in script)
      // Try accessing via grid element's gridstack instance
      const el = document.querySelector('#grid1') as any;
      return el?.gridstack?.getColumn?.();
    });
    expect(cols).toBe(8);
  });

  test('Add widget adds item to grid1', async ({ page }) => {
    const before = await page.locator('#grid1 .grid-stack-item').count();
    await page.getByRole('link', { name: 'Add' }).click();
    await page.waitForTimeout(300);
    const after = await page.locator('#grid1 .grid-stack-item').count();
    expect(after).toBeGreaterThan(before);
  });
});

// ─── grid-lines.html ──────────────────────────────────────────────────────────

test.describe('grid-lines.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/grid-lines.html');
    await page.waitForSelector('#grid', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Grid Lines demo');
    await expect(page.getByRole('heading', { name: /grid lines/i })).toBeVisible();
  });

  test('9 items are rendered (A through I)', async ({ page }) => {
    await expect(page.locator('.grid-stack-item')).toHaveCount(9);
  });

  test('grid has gs-show-grid-lines class initially', async ({ page }) => {
    const classes = await page.locator('#grid').getAttribute('class');
    expect(classes).toContain('gs-show-grid-lines');
  });

  test('toggle checkbox removes grid lines class', async ({ page }) => {
    const checkbox = page.locator('#toggle');
    await checkbox.uncheck();
    await page.waitForTimeout(100);
    const classes = await page.locator('#grid').getAttribute('class');
    expect(classes).not.toContain('gs-show-grid-lines');
  });

  test('re-checking toggle restores grid lines class', async ({ page }) => {
    const checkbox = page.locator('#toggle');
    await checkbox.uncheck();
    await page.waitForTimeout(100);
    await checkbox.check();
    await page.waitForTimeout(100);
    const classes = await page.locator('#grid').getAttribute('class');
    expect(classes).toContain('gs-show-grid-lines');
  });

  test('opacity slider updates badge text', async ({ page }) => {
    const slider = page.locator('#opacity');
    await slider.fill('50');
    // Trigger input event
    await slider.dispatchEvent('input');
    await page.waitForTimeout(100);
    await expect(page.locator('#opacityVal')).toHaveText('50%');
  });

  test('thickness slider updates badge text', async ({ page }) => {
    const slider = page.locator('#thickness');
    await slider.fill('4');
    await slider.dispatchEvent('input');
    await page.waitForTimeout(100);
    await expect(page.locator('#thicknessVal')).toHaveText('4px');
  });

  test('columns slider updates badge text', async ({ page }) => {
    const slider = page.locator('#columns');
    await slider.fill('6');
    await slider.dispatchEvent('input');
    await page.waitForTimeout(200);
    await expect(page.locator('#columnsVal')).toHaveText('6');
  });
});

// ─── right-to-left(rtl).html ──────────────────────────────────────────────────

test.describe('right-to-left(rtl).html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/right-to-left(rtl).html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title', async ({ page }) => {
    await expect(page).toHaveTitle('Right-To-Left (RTL) demo');
  });

  test('html element has dir=rtl', async ({ page }) => {
    const dir = await page.evaluate(() => document.documentElement.getAttribute('dir'));
    expect(dir).toBe('rtl');
  });

  test('grid has grid-stack-rtl class', async ({ page }) => {
    const classes = await page.locator('.grid-stack').getAttribute('class');
    expect(classes).toContain('grid-stack-rtl');
  });

  test('3 initial items are visible', async ({ page }) => {
    await expect(page.locator('.grid-stack-item')).toHaveCount(3);
  });

  test('Add Widget button adds a new item', async ({ page }) => {
    const before = await page.locator('.grid-stack-item').count();
    await page.getByRole('button', { name: 'Add Widget' }).click();
    await page.waitForTimeout(200);
    const after = await page.locator('.grid-stack-item').count();
    expect(after).toBeGreaterThan(before);
  });
});

// ─── transform.html ───────────────────────────────────────────────────────────

test.describe('transform.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/transform.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Transform Parent demo');
    await expect(page.getByRole('heading', { name: /transform/i })).toBeVisible();
  });

  test('scale values are displayed', async ({ page }) => {
    await expect(page.locator('#scale-x')).toBeVisible();
    await expect(page.locator('#scale-y')).toBeVisible();
    const scaleX = await page.locator('#scale-x').textContent();
    const scaleY = await page.locator('#scale-y').textContent();
    expect(parseFloat(scaleX!)).toBeGreaterThan(0);
    expect(parseFloat(scaleY!)).toBeGreaterThan(0);
  });

  test('zoom in increases scale values', async ({ page }) => {
    const beforeX = parseFloat((await page.locator('#scale-x').textContent())!);
    await page.getByRole('link', { name: 'Zoom in' }).click();
    await page.waitForTimeout(100);
    const afterX = parseFloat((await page.locator('#scale-x').textContent())!);
    expect(afterX).toBeGreaterThan(beforeX);
  });

  test('zoom out decreases scale values', async ({ page }) => {
    // First zoom in to ensure we can still zoom out
    await page.getByRole('link', { name: 'Zoom in' }).click();
    await page.waitForTimeout(100);
    const beforeX = parseFloat((await page.locator('#scale-x').textContent())!);
    await page.getByRole('link', { name: 'Zoom out' }).click();
    await page.waitForTimeout(100);
    const afterX = parseFloat((await page.locator('#scale-x').textContent())!);
    expect(afterX).toBeLessThan(beforeX);
  });

  test('Increase Scale X changes scaleX independently', async ({ page }) => {
    const beforeX = parseFloat((await page.locator('#scale-x').textContent())!);
    const beforeY = parseFloat((await page.locator('#scale-y').textContent())!);
    await page.getByRole('link', { name: 'Increase Scale X' }).click();
    await page.waitForTimeout(100);
    const afterX = parseFloat((await page.locator('#scale-x').textContent())!);
    const afterY = parseFloat((await page.locator('#scale-y').textContent())!);
    expect(afterX).toBeGreaterThan(beforeX);
    expect(afterY).toBeCloseTo(beforeY, 2);
  });

  test('action buttons are visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Add Widget' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Zoom in' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Zoom out' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Increase Scale X' })).toBeVisible();
  });

  test('grid has items', async ({ page }) => {
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });
});

// ─── locked.html ──────────────────────────────────────────────────────────────

test.describe('locked.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/locked.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page title and heading', async ({ page }) => {
    await expect(page).toHaveTitle('Locked demo');
    await expect(page.getByRole('heading', { name: /locked/i })).toBeVisible();
  });

  test('Add Widget button is visible', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Add Widget' })).toBeVisible();
  });

  test('float toggle button is visible', async ({ page }) => {
    await expect(page.locator('#float')).toBeVisible();
  });

  test('grid has initial items', async ({ page }) => {
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });

  test('Add Widget button adds an item', async ({ page }) => {
    const before = await page.locator('.grid-stack-item').count();
    await page.getByRole('link', { name: 'Add Widget' }).click();
    await page.waitForTimeout(200);
    const after = await page.locator('.grid-stack-item').count();
    expect(after).toBeGreaterThan(before);
  });
});

// ─── web1.html ────────────────────────────────────────────────────────────────

test.describe('web1.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/web1.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page heading present', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Web demo 1' })).toBeVisible();
  });

  test('11 items are rendered', async ({ page }) => {
    await expect(page.locator('.grid-stack-item')).toHaveCount(11);
  });

  test('all items are visible', async ({ page }) => {
    const items = page.locator('.grid-stack-item');
    for (let i = 0; i < 11; i++) {
      await expect(items.nth(i)).toBeVisible();
    }
  });
});

// ─── web2.html ────────────────────────────────────────────────────────────────

test.describe('web2.html', () => {

  test.beforeEach(async ({ page }) => {
    // Abort CDN requests (Bootstrap, ionicons) to avoid timeouts on mobile emulation
    await page.route('**/unpkg.com/**', route => route.abort());
    await page.route('**/maxcdn.bootstrapcdn.com/**', route => route.abort());
    await page.goto('/demo/web2.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
    await page.waitForSelector('.grid-stack-item', { state: 'visible' });
  });

  test('page heading present', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Advanced Demo' })).toBeVisible();
  });

  test('grid items are rendered', async ({ page }) => {
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });

  test('trash area is present', async ({ page }) => {
    // #trash may be hidden on mobile via Bootstrap d-none class (CDN aborted)
    // Just check it exists in DOM
    const trashCount = await page.locator('#trash').count();
    expect(trashCount).toBeGreaterThan(0);
  });

  test('sidepanel exists in DOM', async ({ page }) => {
    // sidepanel has Bootstrap d-none d-md-block so hidden on mobile
    // Check it exists in DOM
    const sidepanelCount = await page.locator('.sidepanel').count();
    expect(sidepanelCount).toBeGreaterThan(0);
  });

  test('sidepanel drag item exists in DOM', async ({ page }) => {
    const count = await page.locator('.sidepanel .grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });
});

// ─── anijs.html ───────────────────────────────────────────────────────────────

test.describe('anijs.html', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/demo/anijs.html');
    await page.waitForSelector('.grid-stack', { state: 'visible' });
    await page.waitForFunction(() => typeof (window as any).GridStack !== 'undefined');
  });

  test('page title', async ({ page }) => {
    await expect(page).toHaveTitle('AniJS demo');
  });

  test('page heading visible', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'AniJS demo' })).toBeVisible();
  });

  test('Add Widget button is present', async ({ page }) => {
    await expect(page.getByRole('link', { name: 'Add Widget' })).toBeVisible();
  });

  test('grid renders at least one item', async ({ page }) => {
    // The page calls addWidget() on init so there should be at least one item
    await page.waitForSelector('.grid-stack-item', { state: 'visible', timeout: 5000 });
    const count = await page.locator('.grid-stack-item').count();
    expect(count).toBeGreaterThan(0);
  });
});
