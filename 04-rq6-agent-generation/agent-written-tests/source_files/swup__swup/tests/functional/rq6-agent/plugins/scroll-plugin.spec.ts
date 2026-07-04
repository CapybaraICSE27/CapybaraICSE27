import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../../support/swup.js';
import { expectToBeAt, expectNoPageReload, scrollToPosition, expectScrollPosition } from '../../support/commands.js';

/**
 * Tests for the @swup/scroll-plugin integration.
 *
 * The scroll plugin handles smooth scrolling to anchors on navigation.
 * page-1.html has many named anchors inside a .scroll-anchors container
 * (margin: 1000px 0 so they are well off screen).
 */
test.describe('scroll-plugin', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/plugins/scroll-plugin/page-1.html');
		// Wait for the scroll plugin script to load from CDN
		await page.waitForFunction(() => typeof (window as any).SwupScrollPlugin !== 'undefined');
		await waitForSwup(page);
	});

	test('renders page 1 correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Scroll Plugin 1');
		await expect(page.locator('h1')).toContainText('Scroll Plugin 1');
	});

	test('navigates to page 2 without full reload', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="link-to-page"]');
			await page.waitForURL('/plugins/scroll-plugin/page-2.html');
		});
		await expectToBeAt(page, '/plugins/scroll-plugin/page-2.html', 'Scroll Plugin 2');
	});

	test('navigating to a page without hash scrolls to top', async ({ page }) => {
		await scrollToPosition(page, 600);
		await page.click('[data-testid="link-to-page"]');
		await page.waitForURL('/plugins/scroll-plugin/page-2.html');
		await expectScrollPosition(page, 0);
	});

	test('navigating to cross-page anchor scrolls to anchor', async ({ page }) => {
		await page.click('[data-testid="link-to-page-anchor"]');
		await page.waitForURL('/plugins/scroll-plugin/page-2.html#anchor');
		// Anchor is inside .scroll-anchors so should be far from top
		await page.waitForFunction(() => window.scrollY > 0);
		const y = await page.evaluate(() => window.scrollY);
		expect(y).toBeGreaterThan(0);
	});

	test('clicking same-page anchor link scrolls down', async ({ page }) => {
		await page.click('[data-testid="link-to-anchor"]');
		await page.waitForFunction(() => window.scrollY > 0);
		const y = await page.evaluate(() => window.scrollY);
		expect(y).toBeGreaterThan(0);
	});

	test('#top link scrolls to page top', async ({ page }) => {
		await scrollToPosition(page, 800);
		await page.click('[data-testid="link-to-top"]');
		await expectScrollPosition(page, 0);
	});
});
