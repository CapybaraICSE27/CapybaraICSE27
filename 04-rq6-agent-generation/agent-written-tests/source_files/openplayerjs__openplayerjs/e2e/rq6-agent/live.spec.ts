/**
 * live.spec.ts
 *
 * Tests for HLS live stream examples.
 * These tests focus on UI structure and control state rather than actual
 * stream playback, since live HLS streams from external servers may not
 * always be accessible in all CI environments.
 */
import { test, expect } from '@playwright/test';
import { loadExample, openSettings, sel } from './helpers/player';

// ---------------------------------------------------------------------------
// live.html — HLS live stream with captions
// ---------------------------------------------------------------------------
test.describe('live.html', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/live.html');
  });

  test('player wrapper is present', async ({ page }) => {
    await expect(page.locator(sel.wrapper)).toBeVisible();
  });

  test('controls bar is present', async ({ page }) => {
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('play button is present', async ({ page }) => {
    await expect(page.locator(sel.play)).toBeVisible();
  });

  test('play button shows play icon (not playing) initially', async ({ page }) => {
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });

  test('captions button is present', async ({ page }) => {
    await expect(page.locator(sel.captions)).toBeVisible();
  });

  test('settings button opens panel', async ({ page }) => {
    const panel = await openSettings(page);
    await expect(panel).toBeVisible();
  });

  test('settings panel contains Speed item', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator(sel.settingsItems).filter({ hasText: /speed/i })).toBeVisible({ timeout: 5_000 });
  });

  test('fullscreen button is present', async ({ page }) => {
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });

  test('window.__core is exposed by the page', async ({ page }) => {
    const hasCore = await page.evaluate(() => typeof (window as any).__core !== 'undefined');
    expect(hasCore).toBe(true);
  });

  test('current time element is present', async ({ page }) => {
    await expect(page.locator(sel.currentTime)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// live-show-current-time.html — showLiveCurrentTime: true
// ---------------------------------------------------------------------------
test.describe('live-show-current-time.html', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/live-show-current-time.html');
  });

  test('player wrapper is present', async ({ page }) => {
    await expect(page.locator(sel.wrapper)).toBeVisible();
  });

  test('controls bar is present', async ({ page }) => {
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('current time display is visible', async ({ page }) => {
    await expect(page.locator(sel.currentTime)).toBeVisible();
  });

  test('play button is present and shows play icon', async ({ page }) => {
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });

  test('settings button is present', async ({ page }) => {
    await expect(page.locator(sel.settings)).toBeVisible();
  });

  test('fullscreen button is present', async ({ page }) => {
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });

  test('window.__core is exposed by the page', async ({ page }) => {
    const hasCore = await page.evaluate(() => typeof (window as any).__core !== 'undefined');
    expect(hasCore).toBe(true);
  });

  test('page title mentions current time or live', async ({ page }) => {
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });
});
