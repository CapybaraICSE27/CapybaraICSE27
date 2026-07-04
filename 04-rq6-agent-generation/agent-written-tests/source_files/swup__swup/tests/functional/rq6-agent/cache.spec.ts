import { test, expect } from '@playwright/test';

import { waitForSwup, expectSwupToHaveCacheEntry, expectSwupToHaveCacheEntries } from '../support/swup.js';

/**
 * Tests for Swup's in-memory page cache.
 *
 * By default cache is enabled.  After visiting a page Swup stores its HTML so
 * subsequent navigations to that URL skip the network request.
 *
 * NOTE: swup.navigate() is fire-and-forget (returns void), so we must wait for
 * navigation to complete by polling `window._swup.navigating === false` before
 * inspecting the cache.
 */

/** Navigate via Swup and wait until the visit fully completes. */
async function navigateAndWait(page: import('@playwright/test').Page, url: string, opts?: Record<string, unknown>) {
	await page.evaluate(({ url, opts }) => window._swup.navigate(url, opts as any), { url, opts });
	await page.waitForFunction(() => !window._swup.navigating);
}

test.describe('cache: default enabled', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/page-1.html');
		await waitForSwup(page);
	});

	test('cache is empty before any navigation', async ({ page }) => {
		const size = await page.evaluate(() => window._swup.cache.size);
		expect(size).toBe(0);
	});

	test('visited page is cached after navigation', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html');
		await expectSwupToHaveCacheEntry(page, '/page-2.html');
	});

	test('multiple visited pages are all cached', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html');
		await navigateAndWait(page, '/page-3.html');
		await expectSwupToHaveCacheEntries(page, ['/page-2.html', '/page-3.html']);
	});

	test('cached page entry has a url and html property', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html');
		const entry = await page.evaluate(() => window._swup.cache.get('/page-2.html'));
		expect(entry).toBeTruthy();
		expect(entry).toHaveProperty('url', '/page-2.html');
		expect(typeof (entry as any)?.html).toBe('string');
	});

	test('cache size grows with each unique page visit', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html');
		const size1 = await page.evaluate(() => window._swup.cache.size);
		await navigateAndWait(page, '/page-3.html');
		const size2 = await page.evaluate(() => window._swup.cache.size);
		expect(size2).toBeGreaterThan(size1);
	});

	test('revisiting a cached page does not increase cache size', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html');
		const size1 = await page.evaluate(() => window._swup.cache.size);
		await navigateAndWait(page, '/page-2.html');
		const size2 = await page.evaluate(() => window._swup.cache.size);
		expect(size2).toBe(size1);
	});

	test('cache can be cleared programmatically', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html');
		const sizeAfterNav = await page.evaluate(() => window._swup.cache.size);
		expect(sizeAfterNav).toBeGreaterThan(0);
		await page.evaluate(() => window._swup.cache.clear());
		const sizeAfterClear = await page.evaluate(() => window._swup.cache.size);
		expect(sizeAfterClear).toBe(0);
	});
});

test.describe('cache: disabled per-navigation', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/page-1.html');
		await waitForSwup(page);
	});

	test('navigate with cache.write:false does not cache the page', async ({ page }) => {
		await navigateAndWait(page, '/page-2.html', { cache: { read: false, write: false } });
		const entry = await page.evaluate(() => window._swup.cache.get('/page-2.html'));
		expect(entry).toBeFalsy();
	});
});
