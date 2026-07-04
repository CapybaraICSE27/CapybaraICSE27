import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../../support/swup.js';
import { expectToBeAt, expectNoPageReload } from '../../support/commands.js';

/**
 * Tests for the @swup/body-class-plugin integration.
 *
 * page-1.html: <body class="body-1">
 * page-2.html: <body class="body-2">
 *
 * After Swup navigates, the plugin replaces body classes so the body
 * has the class(es) from the incoming page.
 */
test.describe('body-class-plugin', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/plugins/body-class-plugin/page-1.html');
		// Wait for the plugin script to load from CDN
		await page.waitForFunction(() => typeof (window as any).SwupBodyClassPlugin !== 'undefined');
		await waitForSwup(page);
	});

	test('renders page 1 correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Body Class Plugin 1');
		await expect(page.locator('h1')).toContainText('Body Class Plugin 1');
	});

	test('body has body-1 class on page 1', async ({ page }) => {
		await expect(page.locator('body')).toHaveClass(/body-1/);
	});

	test('navigates to page 2 without full reload', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await navigateWithSwup(page, '/plugins/body-class-plugin/page-2.html');
		});
		await expectToBeAt(page, '/plugins/body-class-plugin/page-2.html');
	});

	test('body class updates to body-2 after navigating to page 2', async ({ page }) => {
		await navigateWithSwup(page, '/plugins/body-class-plugin/page-2.html');
		await expectToBeAt(page, '/plugins/body-class-plugin/page-2.html');
		await expect(page.locator('body')).toHaveClass(/body-2/);
	});

	test('body-1 class is removed after navigating to page 2', async ({ page }) => {
		await navigateWithSwup(page, '/plugins/body-class-plugin/page-2.html');
		await expect(page.locator('body')).not.toHaveClass(/body-1/);
	});

	test('navigating back to page 1 restores body-1 class', async ({ page }) => {
		await navigateWithSwup(page, '/plugins/body-class-plugin/page-2.html');
		await navigateWithSwup(page, '/plugins/body-class-plugin/page-1.html');
		await expect(page.locator('body')).toHaveClass(/body-1/);
		await expect(page.locator('body')).not.toHaveClass(/body-2/);
	});
});
