import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { clickOnLink, expectToBeAt, scrollToPosition, expectScrollPosition } from '../support/commands.js';

/**
 * Tests for Swup's built-in scroll behaviour on /scrolling-1.html.
 *
 * Default Swup scrolls to the top of the page on cross-page navigation,
 * and scrolls to named anchors when the URL includes a hash fragment.
 */
test.describe('scrolling: anchor and cross-page', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/scrolling-1.html');
		await waitForSwup(page);
	});

	test('renders correct heading', async ({ page }) => {
		await expect(page.locator('h1')).toContainText('Scrolling 1');
	});

	test('cross-page navigation without hash scrolls to top', async ({ page }) => {
		// Scroll down first, then navigate to a page without hash
		await scrollToPosition(page, 500);
		await navigateWithSwup(page, '/scrolling-2.html');
		await expectToBeAt(page, '/scrolling-2.html');
		await expectScrollPosition(page, 0);
	});

	test('navigates to cross-page anchor and scrolls to it', async ({ page }) => {
		await page.click('[data-testid="link-to-page-anchor"]');
		await expectToBeAt(page, '/scrolling-2.html#anchor');
		// The anchor is inside a .scroll-anchors container with margin:1000px 0
		// so scroll position should be greater than 0
		const y = await page.evaluate(() => window.scrollY);
		expect(y).toBeGreaterThan(0);
	});

	test('cross-page navigation lands at page 2', async ({ page }) => {
		await clickOnLink(page, '/scrolling-2.html');
		await expectToBeAt(page, '/scrolling-2.html', 'Scrolling 2');
	});
});

test.describe('scrolling: same-page hash links', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/scrolling-1.html');
		await waitForSwup(page);
	});

	test('clicking hash link scrolls down within the page', async ({ page }) => {
		await page.click('[data-testid="link-to-anchor"]');
		// Wait for scroll to complete
		await page.waitForFunction(() => window.scrollY > 0);
		const y = await page.evaluate(() => window.scrollY);
		expect(y).toBeGreaterThan(0);
	});

	test('#top hash link scrolls back to page top', async ({ page }) => {
		// Scroll down first
		await scrollToPosition(page, 800);
		await page.click('[data-testid="link-to-top"]');
		await expectScrollPosition(page, 0);
	});
});

test.describe('scrolling: fixture page-2 renders correctly', () => {
	test('page 2 has anchor element', async ({ page }) => {
		await page.goto('/scrolling-2.html');
		await expect(page.locator('[data-testid="anchor"]')).toBeVisible();
	});
});
