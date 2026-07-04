import { test, expect } from '@playwright/test';

import { waitForSwup } from '../support/swup.js';
import { expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for link URL resolution on /link-resolution.html and /nested/ pages.
 *
 * link-resolution.html has:
 *   - Absolute link  /page-2.html
 *   - Relative link  ./../page-2.html
 *   - Self-link      ./link-resolution.html
 *   - External link  https://example.net  (should NOT trigger Swup)
 *
 * nested/nested-1.html uses <base href="/"> so relative links resolve against root.
 */
test.describe('link resolution: absolute and relative links', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/link-resolution.html');
		await waitForSwup(page);
	});

	test('renders page correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Link resolution');
		await expect(page.locator('h1')).toContainText('Link resolution');
	});

	test('absolute link navigates via Swup without reload', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="nav-link-abs"]');
			await page.waitForURL('/page-2.html');
		});
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});

	test('relative link (./../page-2.html) navigates correctly', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="nav-link-rel"]');
			await page.waitForURL('/page-2.html');
		});
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});

	test('self-link navigates to same page via Swup', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="nav-link-self"]');
			await page.waitForURL('/link-resolution.html');
		});
		await expectToBeAt(page, '/link-resolution.html');
	});

	test('external link is NOT intercepted by Swup', async ({ page }) => {
		// We just verify the href is external — clicking would navigate away
		const href = await page.locator('[data-testid="nav-link-ext"]').getAttribute('href');
		expect(href).toBe('https://example.net');
	});
});

/**
 * Nested pages (/nested/nested-1.html and /nested/nested-2.html) load
 * Swup.umd.js but do NOT call `new Swup()`.  We initialise Swup manually
 * after a direct page.goto() so the full page DOM (header + container) is
 * available for interaction.
 */
test.describe('link resolution: nested pages with <base href="/">', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/nested/nested-1.html');
		// Initialise Swup manually — the fixture relies on a caller doing this
		await page.evaluate(() => { (window as any)._swup = new (window as any).Swup(); });
		await waitForSwup(page);
	});

	test('renders nested page 1 correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Nested Page 1');
		await expect(page.locator('h1')).toContainText('Nested Page 1');
	});

	test('navigates to nested page 2 via link', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="nav-link-sub"]');
			await expect(page).toHaveURL('/nested/nested-2.html');
		});
		await expect(page.locator('h1')).toContainText('Nested Page 2');
	});

	test('can navigate back from nested-2 to nested-1', async ({ page }) => {
		await page.click('[data-testid="nav-link-sub"]');
		await expect(page).toHaveURL('/nested/nested-2.html');
		await page.waitForSelector('html:not(.is-changing)');
		await page.click('a[href="nested/nested-1.html"]');
		await expect(page).toHaveURL('/nested/nested-1.html');
		await page.waitForSelector('html:not(.is-changing)');
		await expect(page.locator('h1')).toContainText('Nested Page 1');
	});
});
