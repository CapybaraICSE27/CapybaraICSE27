/**
 * source-management.spec.ts
 *
 * Tests for source fallback (source-fallback.html) and dynamic source
 * switching (src-switch.html).
 */
import { test, expect } from '@playwright/test';
import { loadExample, sel } from './helpers/player';

// ---------------------------------------------------------------------------
// source-fallback.html
// ---------------------------------------------------------------------------
test.describe('source-fallback.html', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/source-fallback.html');
  });

  test('#status div is visible with non-empty text', async ({ page }) => {
    // Status starts as "Waiting…" but the broken source fails immediately so
    // it may already read "Fallback: …" — either is valid.
    await expect(page.locator('#status')).toBeVisible();
    await expect(page.locator('#status')).toHaveText(/.+/);
  });

  test('fallback triggers and #status updates within timeout', async ({ page }) => {
    // After the broken first source fails, the fallback fires and updates #status
    await expect(page.locator('#status')).toHaveText(/Fallback:|Error:/, {
      timeout: 20_000,
    });
  });

  test('player wrapper stays visible after fallback', async ({ page }) => {
    // Wait for fallback to process
    await expect(page.locator('#status')).toHaveText(/Fallback:|Error:/, {
      timeout: 20_000,
    });
    await expect(page.locator(sel.wrapper)).toBeVisible();
  });

  test('controls remain functional after fallback', async ({ page }) => {
    await expect(page.locator('#status')).toHaveText(/Fallback:|Error:/, {
      timeout: 20_000,
    });
    // Controls bar should still be visible
    await expect(page.locator(sel.controls)).toBeVisible();
    await expect(page.locator(sel.play)).toBeVisible();
  });

  test('window.__core is set by the example script', async ({ page }) => {
    const hasCore = await page.evaluate(() => typeof window.__core !== 'undefined');
    expect(hasCore).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// src-switch.html
// ---------------------------------------------------------------------------
test.describe('src-switch.html', () => {
  test.beforeEach(async ({ page }) => {
    await loadExample(page, '/examples/src-switch.html');
  });

  test('"Switch source" button is visible and enabled', async ({ page }) => {
    const btn = page.getByTestId('btn-switch');
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });

  test('"Restore source" button is visible and enabled', async ({ page }) => {
    const btn = page.getByTestId('btn-restore');
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });

  test('clicking "Switch source" updates window.__core.src', async ({ page }) => {
    const SOURCE_B = 'https://playertest.longtailvideo.com/adaptive/progdatime/playlist2.m3u8';
    await page.getByTestId('btn-switch').click();
    // core.src should be updated to SOURCE_B
    await expect
      .poll(() => page.evaluate(() => (window as any).__core?.src), {
        timeout: 10_000,
        message: 'Expected core.src to be updated to SOURCE_B',
      })
      .toBe(SOURCE_B);
  });

  test('clicking "Restore source" resets window.__core.src', async ({ page }) => {
    const SOURCE_A = 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8';
    // Switch then restore
    await page.getByTestId('btn-switch').click();
    await page.getByTestId('btn-restore').click();
    await expect
      .poll(() => page.evaluate(() => (window as any).__core?.src), {
        timeout: 10_000,
        message: 'Expected core.src to be restored to SOURCE_A',
      })
      .toBe(SOURCE_A);
  });

  test('player remains functional after source switch', async ({ page }) => {
    await page.getByTestId('btn-switch').click();
    // Player wrapper and controls must still be present
    await expect(page.locator(sel.wrapper)).toBeVisible();
    await expect(page.locator(sel.controls)).toBeVisible();
  });
});
