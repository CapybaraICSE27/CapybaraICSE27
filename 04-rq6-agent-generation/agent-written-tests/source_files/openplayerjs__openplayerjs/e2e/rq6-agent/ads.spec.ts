/**
 * ads.spec.ts
 *
 * Tests for ad-enabled example pages.
 * NOTE: Ad delivery depends on external DoubleClick / IMA servers.
 * Tests here verify the player UI structure and that the player renders
 * correctly in the presence of the AdsPlugin — not that a specific ad plays.
 */
import { test, expect } from '@playwright/test';
import { loadExample, sel } from './helpers/player';

// ---------------------------------------------------------------------------
// ads.html — VMAP pre/mid/post-roll
// ---------------------------------------------------------------------------
test.describe('ads.html — VMAP schedule', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/ads.html');
  });

  test('player wrapper is present', async ({ page }) => {
    await expect(page.locator(sel.wrapper)).toBeVisible();
  });

  test('controls bar is present', async ({ page }) => {
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('play button is visible', async ({ page }) => {
    await expect(page.locator(sel.play)).toBeVisible();
  });

  test('settings and fullscreen buttons are visible', async ({ page }) => {
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });

  test('page title identifies the example', async ({ page }) => {
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('play button starts in non-playing state', async ({ page }) => {
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });

  test('video source element is present in DOM', async ({ page }) => {
    // The underlying <video> should be attached (even if the ad container overlays it)
    await expect(page.locator('video')).toBeAttached();
  });
});

// ---------------------------------------------------------------------------
// captions.html — VAST preroll with inline VTT captions
// ---------------------------------------------------------------------------
test.describe('captions.html — VAST preroll + caption tracks', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/captions.html');
  });

  test('player wrapper is present', async ({ page }) => {
    await expect(page.locator(sel.wrapper)).toBeVisible();
  });

  test('captions button is visible', async ({ page }) => {
    await expect(page.locator(sel.captions)).toBeVisible();
  });

  test('page has a <track> element with kind=subtitles', async ({ page }) => {
    // The HTML has a <track kind="subtitles" srclang="en" label="English">
    await expect(page.locator('track[kind="subtitles"]')).toBeAttached();
  });

  test('track has lang="en"', async ({ page }) => {
    await expect(page.locator('track[srclang="en"]')).toBeAttached();
  });

  test('play button is visible', async ({ page }) => {
    await expect(page.locator(sel.play)).toBeVisible();
  });

  test('video source element is present in DOM', async ({ page }) => {
    await expect(page.locator('video')).toBeAttached();
  });

  test('progress bar is present', async ({ page }) => {
    await expect(page.locator(sel.progress)).toBeVisible();
  });
});
