import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { clickOnLink, expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for basic SPA navigation between page-1/2/3 fixtures.
 * Verifies link clicks, API navigation, title/heading updates, and that
 * Swup intercepts links without full page reloads.
 */
test.describe('navigation: basic pages', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/page-1.html');
		await waitForSwup(page);
	});

	test('page 1 has correct title and heading', async ({ page }) => {
		await expect(page).toHaveTitle('Page 1');
		await expect(page.locator('h1')).toContainText('Page 1');
	});

	test('navigates to page 2 without full reload', async ({ page }) => {
		await expectNoPageReload(page, () => clickOnLink(page, '/page-2.html'));
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});

	test('navigates to page 3 without full reload', async ({ page }) => {
		await expectNoPageReload(page, () => clickOnLink(page, '/page-3.html'));
		await expectToBeAt(page, '/page-3.html', 'Page 3');
	});

	test('navigates page-1 → page-2 → page-3 in sequence', async ({ page }) => {
		await clickOnLink(page, '/page-2.html');
		await expectToBeAt(page, '/page-2.html', 'Page 2');
		await clickOnLink(page, '/page-3.html');
		await expectToBeAt(page, '/page-3.html', 'Page 3');
	});

	test('data-testid link to page-2 navigates correctly', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});

	test('data-testid link to page-3 navigates correctly', async ({ page }) => {
		await page.click('[data-testid="link-to-page-3"]');
		await expectToBeAt(page, '/page-3.html', 'Page 3');
	});

	test('navigates back to page-1 via header link after going to page-2', async ({ page }) => {
		await clickOnLink(page, '/page-2.html');
		await expectToBeAt(page, '/page-2.html');
		await page.click('a[href="/page-1.html"]');
		await expectToBeAt(page, '/page-1.html', 'Page 1');
	});

	test('programmatic navigate() works', async ({ page }) => {
		await expectNoPageReload(page, () => navigateWithSwup(page, '/page-3.html'));
		await expectToBeAt(page, '/page-3.html', 'Page 3');
	});

	test('document title updates on each navigation', async ({ page }) => {
		await clickOnLink(page, '/page-2.html');
		await expect(page).toHaveTitle('Page 2');
		await clickOnLink(page, '/page-3.html');
		await expect(page).toHaveTitle('Page 3');
	});

	test('swup-enabled class persists across navigations', async ({ page }) => {
		await clickOnLink(page, '/page-2.html');
		await expect(page.locator('html')).toHaveClass(/swup-enabled/);
		await clickOnLink(page, '/page-3.html');
		await expect(page.locator('html')).toHaveClass(/swup-enabled/);
	});

	test('data-swup-animation link navigates correctly', async ({ page }) => {
		// page-1 has <a href="/page-2.html" data-swup-animation="link">
		await page.click('a[data-swup-animation="link"]');
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});

	test('container content is replaced after navigation', async ({ page }) => {
		const container = page.locator('[data-testid="container"]');
		await expect(container.locator('h1')).toContainText('Page 1');
		await clickOnLink(page, '/page-2.html');
		await expect(container.locator('h1')).toContainText('Page 2');
	});

	test('visit:start and visit:end hooks fire on navigation', async ({ page }) => {
		const events = await page.evaluate(() => {
			return new Promise<string[]>((resolve) => {
				const fired: string[] = [];
				window._swup.hooks.on('visit:start', () => fired.push('start'));
				window._swup.hooks.on('visit:end', () => {
					fired.push('end');
					resolve(fired);
				});
				window._swup.navigate('/page-2.html');
			});
		});
		expect(events).toContain('start');
		expect(events).toContain('end');
		expect(events.indexOf('start')).toBeLessThan(events.indexOf('end'));
	});
});
