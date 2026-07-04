import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { clickOnLink, expectToBeAt } from '../support/commands.js';

/**
 * Tests for /animation-native.html — Swup initialized with { native: true }.
 *
 * When the browser supports the View Transitions API, Swup adds a `swup-native`
 * class to <html> during transitions.  When it does not support it, Swup falls
 * back to its CSS-transition mechanism transparently.
 */
test.describe('native mode', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/animation-native.html');
		await waitForSwup(page);
	});

	test('renders correct title and heading', async ({ page }) => {
		await expect(page).toHaveTitle('Animation duration: native');
		await expect(page.locator('h1')).toContainText('Animation duration: native');
	});

	test('swup is initialized with native option', async ({ page }) => {
		const isNative = await page.evaluate(() => window._swup.options.native);
		expect(isNative).toBe(true);
	});

	test('navigates via link click', async ({ page }) => {
		await clickOnLink(page, '/animation-duration.html');
		await expectToBeAt(page, '/animation-duration.html', 'Animation duration');
	});

	test('navigates via API', async ({ page }) => {
		await navigateWithSwup(page, '/animation-complex.html');
		await expectToBeAt(page, '/animation-complex.html');
		await expect(page.locator('h1')).toContainText('Animation duration: complex');
	});

	test('animation classes are cleaned up after navigation', async ({ page }) => {
		await navigateWithSwup(page, '/animation-duration.html');
		await page.waitForSelector('html:not(.is-changing)');
		const html = page.locator('html');
		await expect(html).not.toHaveClass(/is-changing/);
		await expect(html).not.toHaveClass(/is-animating/);
	});

	test('can navigate back from another page to native page', async ({ page }) => {
		await navigateWithSwup(page, '/animation-duration.html');
		await expectToBeAt(page, '/animation-duration.html');
		await navigateWithSwup(page, '/animation-native.html');
		await expectToBeAt(page, '/animation-native.html');
		await expect(page.locator('h1')).toContainText('Animation duration: native');
	});
});
