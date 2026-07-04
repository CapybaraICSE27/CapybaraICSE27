import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup, expectSwupToHaveCacheEntry } from '../support/swup.js';
import { clickOnLink, expectToBeAt } from '../support/commands.js';

/**
 * Tests for server-side redirect handling.
 *
 * serve.json maps: /redirect-2.html → /redirect-3.html (301)
 *
 * When Swup fetches /redirect-2.html, the server redirects to /redirect-3.html.
 * Swup follows the redirect, renders redirect-3's content, and updates the URL
 * to the final destination.
 */
test.describe('redirects: server-side 301', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/redirect-1.html');
		await waitForSwup(page);
	});

	test('renders redirect-1 page correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Redirect 1');
		await expect(page.locator('h1')).toContainText('Redirect 1');
	});

	test('navigating to redirect-2 lands at redirect-3 (follows server redirect)', async ({ page }) => {
		await navigateWithSwup(page, '/redirect-2.html');
		// Swup follows the 301 from redirect-2 → redirect-3
		await expectToBeAt(page, '/redirect-3.html');
	});

	test('redirect destination content is rendered', async ({ page }) => {
		await navigateWithSwup(page, '/redirect-2.html');
		await expect(page.locator('h1')).toContainText('Redirect 3');
	});

	test('navigating directly to redirect-3 works', async ({ page }) => {
		await navigateWithSwup(page, '/redirect-3.html');
		await expectToBeAt(page, '/redirect-3.html', 'Redirect 3');
	});

	test('can navigate back to redirect-1 from redirect-3', async ({ page }) => {
		await navigateWithSwup(page, '/redirect-3.html');
		await clickOnLink(page, '/redirect-1.html');
		await expectToBeAt(page, '/redirect-1.html', 'Redirect 1');
	});

	test('neither redirect source nor target is cached after a redirect', async ({ page }) => {
		// fetchPage only caches when the response URL equals the requested URL.
		// For a server redirect (redirect-2 → redirect-3) the URLs differ,
		// so Swup intentionally does NOT write to the cache.
		await page.evaluate(() => window._swup.navigate('/redirect-2.html'));
		await page.waitForFunction(() => !window._swup.navigating);
		const entry2 = await page.evaluate(() => window._swup.cache.get('/redirect-2.html'));
		const entry3 = await page.evaluate(() => window._swup.cache.get('/redirect-3.html'));
		expect(entry2).toBeFalsy();
		expect(entry3).toBeFalsy();
	});
});
