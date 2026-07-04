import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

/**
 * Basic accessibility and contrast checks for key UI components.
 */
test.describe('Accessibility & ARIA', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('app-root has lang attribute on html element', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const lang = await page.locator('html').getAttribute('lang');
    // App sets lang attribute (from Angular i18n)
    expect(lang).toBeTruthy();
  });

  test('side navigation has role="navigation"', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const nav = page.locator('magic-side-nav nav[role="navigation"]');
    await expect(nav).toBeAttached();
  });

  test('nav items have role="listitem"', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const listItems = page.locator('nav[role="navigation"] li[role="listitem"]');
    const count = await listItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test('done-toggle has correct ARIA attributes', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const firstToggle = page.locator('task done-toggle').first();
    await expect(firstToggle).toHaveAttribute('role', 'checkbox');
    await expect(firstToggle).toHaveAttribute('aria-label', 'Toggle completion status');
    await expect(firstToggle).toHaveAttribute('aria-checked');
  });

  test('config tabs have correct role="tab" ARIA', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(6);

    // Active tab should have aria-selected="true"
    const activeTabs = page.locator('[role="tab"][aria-selected="true"]');
    await expect(activeTabs).toHaveCount(1);
  });

  test('nav mode toggle button has aria-label', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const modeToggle = page.locator('magic-side-nav .mode-toggle');
    const ariaLabel = await modeToggle.getAttribute('aria-label');
    expect(ariaLabel).toBeTruthy();
    expect(ariaLabel).toMatch(/compact|full|mode|switch/i);
  });

  test('sidebar nav list has role="list"', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const navList = page.locator('ul[role="list"]');
    await expect(navList).toBeAttached();
  });
});

test.describe('Contrast Test Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Contrast Test page shows button type sections', async ({ page }) => {
    await page.goto('/#/contrast-test');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Text Buttons|Raised Buttons|Flat Buttons|Icon Buttons/i);
  });

  test('Contrast Test page has Tabs section', async ({ page }) => {
    await page.goto('/#/contrast-test');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Tabs/i);
  });

  test('Contrast Test page renders FAB buttons', async ({ page }) => {
    await page.goto('/#/contrast-test');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/FAB|mat-fab/i);
  });
});
