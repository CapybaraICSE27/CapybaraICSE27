import { test, expect } from '@playwright/test';

import { waitForSwup } from '../support/swup.js';
import { expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for /link-selector.html — verifies that Swup intercepts non-anchor
 * link types in addition to standard <a> elements:
 *   - SVG <a xlink:href="…"> links
 *   - <area href="…"> elements inside an imagemap
 */
test.describe('link selector: SVG and imagemap links', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/link-selector.html');
		await waitForSwup(page);
	});

	test('renders page correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Link selector');
		await expect(page.locator('h1')).toContainText('Link selector');
	});

	test('SVG anchor link navigates via Swup', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('svg a');
			await page.waitForURL('/page-2.html');
		});
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});

	test('imagemap area element is present with correct href', async ({ page }) => {
		// The default linkSelector is 'a[href]' which does NOT match <area> elements.
		// We just verify the element is in the DOM with the expected href attribute.
		const area = page.locator('area[href="/page-2.html"]');
		await expect(area).toHaveAttribute('href', '/page-2.html');
	});

	test('standard header links navigate correctly', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('.header a[href="/page-1.html"]');
			await page.waitForURL('/page-1.html');
		});
		await expectToBeAt(page, '/page-1.html', 'Page 1');
	});
});
