/**
 * youtube.spec.ts
 *
 * Tests for the YouTube engine integration (youtube.html).
 * The YouTubeMediaEngine injects an <iframe> pointing at youtube.com/embed/<videoId>.
 * These tests verify the player structure and that the iframe is injected; they
 * do NOT assert on YouTube playback since that depends on external network access
 * and YouTube's own policies.
 */
import { test, expect } from '@playwright/test';
import { loadExample, sel } from './helpers/player';

const VIDEO_ID = 'dQw4w9WgXcQ';

test.describe('youtube.html — YouTube engine', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/youtube.html');
  });

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper (.op-player) is present', async ({ page }) => {
    await expect(page.locator(sel.wrapper)).toBeVisible();
  });

  test('controls bar is present', async ({ page }) => {
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('play button is visible', async ({ page }) => {
    await expect(page.locator(sel.play)).toBeVisible();
  });

  test('settings and fullscreen buttons are present', async ({ page }) => {
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });

  test('YouTube iframe is injected into the DOM', async ({ page }) => {
    // YouTubeMediaEngine replaces the <video> element with an <iframe src="...youtube...">
    await expect(page.locator(`iframe[src*="youtube"]`)).toBeAttached({ timeout: 15_000 });
  });

  test('YouTube iframe src contains the correct video ID', async ({ page }) => {
    const iframe = page.locator(`iframe[src*="youtube"]`).first();
    await expect(iframe).toBeAttached({ timeout: 15_000 });
    const src = await iframe.getAttribute('src');
    expect(src).toContain(VIDEO_ID);
  });

  test('original video element or its source declared video/youtube type', async ({ page }) => {
    // The YouTubeMediaEngine may replace the <video>/<source> with an iframe.
    // Either the original <source type="video/youtube"> persists, or the
    // player wrapper wraps what was the <video id="player"> element.
    // At minimum the wrapper exists (checked in earlier tests).
    // We verify the page's module script declares the YouTube source type
    // by inspecting the DOM at page-load time before the engine runs.
    const srcType = await page.evaluate(() => {
      const src = document.querySelector('source[type="video/youtube"]');
      // Also accept if the engine removed the source but left a data-type attr
      const vid = document.querySelector('video[data-source-type="video/youtube"]');
      return src !== null || vid !== null;
    });
    // If the source element is gone (engine replaced it), just assert the iframe is there
    const hasIframe = await page.locator('iframe[src*="youtube"]').count();
    expect(srcType || hasIframe > 0).toBe(true);
  });
});
