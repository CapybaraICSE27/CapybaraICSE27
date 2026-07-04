/**
 * pages.spec.ts
 *
 * Structural smoke tests for every example page.
 * These tests do NOT require video to actually play — they verify that the
 * page loads, the correct title is set, and the expected DOM elements are
 * present after the player initialises.
 */
import { test, expect } from '@playwright/test';
import { loadExample, sel } from './helpers/player';

// ---------------------------------------------------------------------------
// core.html — bare Core usage without createUI()
// ---------------------------------------------------------------------------
test.describe('/examples/core.html', () => {
  test('page loads and video element is present', async ({ page }) => {
    await page.goto('/examples/core.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
    // core.html does NOT call createUI() so there is no .op-player wrapper
    await expect(page.locator('#player')).toBeVisible({ timeout: 10_000 });
  });

  test('contains registerPlugin() explainer text', async ({ page }) => {
    await page.goto('/examples/core.html');
    await expect(page.locator('p')).toContainText('registerPlugin()', { timeout: 5_000 });
  });
});

// ---------------------------------------------------------------------------
// basic.html — HLS + VAST skippable preroll
// ---------------------------------------------------------------------------
test.describe('/examples/basic.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/basic.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls bar are present', async ({ page }) => {
    await loadExample(page, '/examples/basic.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('play, volume, settings and fullscreen buttons are present', async ({ page }) => {
    await loadExample(page, '/examples/basic.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });

  test('progress bar is present', async ({ page }) => {
    await loadExample(page, '/examples/basic.html');
    await expect(page.locator(sel.progress)).toBeVisible();
  });

  test('basic.html does NOT have captions button (not in buildControls)', async ({ page }) => {
    await loadExample(page, '/examples/basic.html');
    await expect(page.locator(sel.captions)).not.toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// ads.html — VMAP pre/mid/post-roll
// ---------------------------------------------------------------------------
test.describe('/examples/ads.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/ads.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/ads.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/ads.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// captions.html — VAST preroll with VTT caption tracks
// ---------------------------------------------------------------------------
test.describe('/examples/captions.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/captions.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/captions.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('captions button is present (included in buildControls)', async ({ page }) => {
    await loadExample(page, '/examples/captions.html');
    await expect(page.locator(sel.captions)).toBeVisible();
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/captions.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// live.html — HLS live stream
// ---------------------------------------------------------------------------
test.describe('/examples/live.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/live.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/live.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('captions button is present (captions track in HTML)', async ({ page }) => {
    await loadExample(page, '/examples/live.html');
    await expect(page.locator(sel.captions)).toBeVisible();
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/live.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// live-show-current-time.html — HLS live + showLiveCurrentTime
// ---------------------------------------------------------------------------
test.describe('/examples/live-show-current-time.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/live-show-current-time.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/live-show-current-time.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('time display element is present', async ({ page }) => {
    await loadExample(page, '/examples/live-show-current-time.html');
    await expect(page.locator(sel.currentTime)).toBeVisible();
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/live-show-current-time.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// multiplugin.html — chapters + chapterUi plugins + HLS
// ---------------------------------------------------------------------------
test.describe('/examples/multiplugin.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/multiplugin.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/multiplugin.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('chapter banner element is injected by chapterUi plugin', async ({ page }) => {
    await loadExample(page, '/examples/multiplugin.html');
    // The chapterUiPlugin creates a .chapter-banner div inside the player
    await expect(page.locator('.chapter-banner')).toBeAttached({ timeout: 10_000 });
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/multiplugin.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// source-fallback.html — broken first source → fallback to second
// ---------------------------------------------------------------------------
test.describe('/examples/source-fallback.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/source-fallback.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/source-fallback.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('#status element is visible', async ({ page }) => {
    await loadExample(page, '/examples/source-fallback.html');
    await expect(page.locator('#status')).toBeVisible();
    // The status text starts as "Waiting…" but may have already updated to
    // "Fallback: …" by the time we check (the broken source fails very fast).
    await expect(page.locator('#status')).toHaveText(/.+/);
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/source-fallback.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// src-switch.html — dynamic source switching via buttons
// ---------------------------------------------------------------------------
test.describe('/examples/src-switch.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/src-switch.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/src-switch.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('switch source and restore source buttons are visible', async ({ page }) => {
    await loadExample(page, '/examples/src-switch.html');
    await expect(page.getByTestId('btn-switch')).toBeVisible();
    await expect(page.getByTestId('btn-restore')).toBeVisible();
  });

  test('play, volume, settings and fullscreen buttons present', async ({ page }) => {
    await loadExample(page, '/examples/src-switch.html');
    await expect(page.locator(sel.play)).toBeVisible();
    await expect(page.locator(sel.volume)).toBeVisible();
    await expect(page.locator(sel.settings)).toBeVisible();
    await expect(page.locator(sel.fullscreen)).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// youtube.html — YouTube engine + AdsPlugin
// ---------------------------------------------------------------------------
test.describe('/examples/youtube.html', () => {
  test('page loads with correct title', async ({ page }) => {
    await loadExample(page, '/examples/youtube.html');
    await expect(page).toHaveTitle(/OpenPlayerJS/i);
  });

  test('player wrapper and controls are present', async ({ page }) => {
    await loadExample(page, '/examples/youtube.html');
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });

  test('YouTube iframe is injected by YouTubeMediaEngine', async ({ page }) => {
    await loadExample(page, '/examples/youtube.html');
    // The YouTube engine replaces the <video> with (or adds alongside it) an iframe
    // pointing at youtube.com/embed/<videoId>
    await expect(page.frameLocator('iframe[src*="youtube"]').locator('body'))
      .toBeAttached({
        timeout: 15_000,
      })
      .catch(() => {
        // If YouTube is blocked in the test environment, fall back to checking
        // that an iframe pointing at youtube exists in the DOM
      });
    // At minimum the iframe must exist in the DOM
    await expect(page.locator('iframe[src*="youtube"]')).toBeAttached({ timeout: 15_000 });
  });
});
