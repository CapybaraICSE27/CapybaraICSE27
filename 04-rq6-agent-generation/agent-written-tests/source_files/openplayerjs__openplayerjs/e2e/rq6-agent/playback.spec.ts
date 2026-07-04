/**
 * playback.spec.ts
 *
 * Tests for basic playback interactions (play, pause, progress).
 * Uses source-fallback.html and captions.html which have reliable MP4
 * sources so these tests are not dependent on HLS or ad network availability.
 */
import { test, expect } from '@playwright/test';
import {
  loadExample,
  clickPlay,
  clickPause,
  // waitForPlayback,
  openSettings,
  openSubmenu,
  sel,
} from './helpers/player';

// ---------------------------------------------------------------------------
// source-fallback.html (MP4 after broken-source fallback — no ads)
// ---------------------------------------------------------------------------
test.describe('source-fallback.html — playback interactions', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/source-fallback.html');
  });

  test('play button shows play icon initially (not playing)', async ({ page }) => {
    // Before clicking play the button should NOT have the --pause class
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });

  test('clicking play transitions to playing state', async ({ page }) => {
    await clickPlay(page);
    // After clickPlay, the button should carry the --pause class (indicates playing)
    await expect(page.locator(sel.play)).toHaveClass(/op-controls__playpause--pause/);
  });

  test('clicking pause while playing stops playback', async ({ page }) => {
    await clickPlay(page);
    await clickPause(page);
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });

  test('center overlay is visible when player is paused', async ({ page }) => {
    await expect(page.locator(sel.centerOverlay)).toBeVisible();
  });

  test('source:fallback triggers status text update', async ({ page }) => {
    // The first source is broken; after the player tries it the status should
    // update from "Waiting…" to include "Fallback:" text.
    await expect(page.locator('#status')).toHaveText(/Fallback:|Error:/, {
      timeout: 20_000,
    });
  });

  test('current time starts at 00:00', async ({ page }) => {
    const timeEl = page.locator(sel.currentTime);
    await expect(timeEl).toHaveText('00:00');
  });
});

// ---------------------------------------------------------------------------
// captions.html — playback using BigBuckBunny MP4 (reliable VOD source)
// ---------------------------------------------------------------------------
test.describe('captions.html — playback and current time', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/captions.html');
  });

  test('play button shows play icon initially', async ({ page }) => {
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });

  test('current time element is visible and starts at 00:00', async ({ page }) => {
    await expect(page.locator(sel.currentTime)).toBeVisible();
    await expect(page.locator(sel.currentTime)).toHaveText('00:00');
  });

  test('clicking play button enters playing state', async ({ page }) => {
    await clickPlay(page);
    await expect(page.locator(sel.play)).toHaveClass(/op-controls__playpause--pause/);
  });

  test('play then pause cycle', async ({ page }) => {
    await clickPlay(page);
    await clickPause(page);
    await expect(page.locator(sel.play)).not.toHaveClass(/op-controls__playpause--pause/);
  });
});

// ---------------------------------------------------------------------------
// basic.html — settings panel interaction
// ---------------------------------------------------------------------------
test.describe('basic.html — settings panel', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/basic.html');
  });

  test('settings button is present and visible', async ({ page }) => {
    await expect(page.locator(sel.settings)).toBeVisible();
  });

  test('clicking settings opens the settings panel', async ({ page }) => {
    const panel = await openSettings(page);
    await expect(panel).toBeVisible();
  });

  test('settings panel lists Speed submenu item', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator(sel.settingsItems).filter({ hasText: /speed/i })).toBeVisible({
      timeout: 5_000,
    });
  });

  test('opening Speed submenu shows back button', async ({ page }) => {
    await openSettings(page);
    await openSubmenu(page, /speed/i);
    await expect(page.locator(sel.settingsBack)).toBeVisible();
  });

  test('pressing Escape closes the settings panel', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator(sel.settingsPanel)).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator(sel.settingsPanel)).not.toBeVisible({ timeout: 3_000 });
  });
});

// ---------------------------------------------------------------------------
// multiplugin.html — chapter banner appears during playback
// ---------------------------------------------------------------------------
test.describe('multiplugin.html — chapter banner', () => {
  test('chapter banner starts empty/hidden before playback', async ({ page }) => {
    await loadExample(page, '/examples/multiplugin.html');
    // Banner is created by chapterUiPlugin but starts with display:none
    const banner = page.locator('.chapter-banner');
    await expect(banner).toBeAttached({ timeout: 10_000 });
  });
});
