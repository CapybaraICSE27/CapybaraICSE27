import { test, expect } from '@playwright/test';

import { waitForSwup } from '../support/swup.js';
import { expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for the Alpine.js integration fixture pages (/alpinejs/).
 *
 * The Alpine component listens for:
 *   - swup:link:click → sets clickFired → adds class click-fired
 *   - swup:any        → sets anyFired   → adds class any-fired
 *
 * We wait for Alpine to initialise (deferred script from CDN) before asserting.
 */
test.describe('alpinejs integration', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/alpinejs/page-1.html');
		// Wait for Alpine to load and initialise
		await page.waitForFunction(() => typeof (window as any).Alpine !== 'undefined');
		await waitForSwup(page);
	});

	test('renders page 1 correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Page 1');
		await expect(page.locator('#swup h1')).toContainText('Page 1');
	});

	test('alpine component is present', async ({ page }) => {
		await expect(page.locator('.alpine-component')).toBeVisible();
	});

	test('swup:link:click adds click-fired class to alpine component', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		// After a link click the Alpine component should have click-fired class
		await expect(page.locator('.alpine-component')).toHaveClass(/click-fired/);
	});

	test('swup:any event fires and any-fired class is added', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await page.waitForURL('/alpinejs/page-2.html');
		// any-fired class should be set because multiple swup:any events fired
		await expect(page.locator('.alpine-component')).toHaveClass(/any-fired/);
	});

	test('navigates to page 2 without full reload', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="link-to-page-2"]');
			await page.waitForURL('/alpinejs/page-2.html');
		});
		await expectToBeAt(page, '/alpinejs/page-2.html', 'Page 2');
	});

	test('page 2 has its own alpine component', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await page.waitForURL('/alpinejs/page-2.html');
		await expect(page.locator('.alpine-component')).toBeVisible();
	});
});
