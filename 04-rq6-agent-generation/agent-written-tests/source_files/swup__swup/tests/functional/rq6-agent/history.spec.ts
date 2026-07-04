import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for history management (pushState vs replaceState).
 *
 * history.html has:
 *   - "Page 3: create"  → data-swup-history not set  → pushState (adds a new entry)
 *   - "Page 3: update"  → data-swup-history="replace" → replaceState (overwrites current entry)
 */
test.describe('history: pushState and replaceState', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/history.html');
		await waitForSwup(page);
	});

	test('renders history page correctly', async ({ page }) => {
		await expect(page).toHaveTitle('History');
		await expect(page.locator('h1')).toContainText('History');
	});

	test('normal link navigation uses pushState (history length increases)', async ({ page }) => {
		const before = await page.evaluate(() => window.history.length);
		await page.click('[data-testid="create-link"]');
		await expectToBeAt(page, '/page-3.html');
		const after = await page.evaluate(() => window.history.length);
		expect(after).toBe(before + 1);
	});

	test('data-swup-history="replace" uses replaceState (history length unchanged)', async ({ page }) => {
		const before = await page.evaluate(() => window.history.length);
		await page.click('[data-testid="update-link"]');
		await expectToBeAt(page, '/page-3.html');
		const after = await page.evaluate(() => window.history.length);
		expect(after).toBe(before);
	});

	test('pushState navigation: browser back returns to history page', async ({ page }) => {
		await page.click('[data-testid="create-link"]');
		await expectToBeAt(page, '/page-3.html');
		await page.goBack();
		await expectToBeAt(page, '/history.html');
	});

	test('page content updates correctly on pushState navigation', async ({ page }) => {
		await page.click('[data-testid="create-link"]');
		await expect(page.locator('h1')).toContainText('Page 3');
	});

	test('page content updates correctly on replaceState navigation', async ({ page }) => {
		await page.click('[data-testid="update-link"]');
		await expect(page.locator('h1')).toContainText('Page 3');
	});

	test('popstate event triggers swup navigation', async ({ page }) => {
		// Navigate forward first
		await page.click('[data-testid="create-link"]');
		await expectToBeAt(page, '/page-3.html');

		// Then go back — swup should handle the popstate
		await expectNoPageReload(page, () => page.goBack());
		await expectToBeAt(page, '/history.html');
		await expect(page.locator('h1')).toContainText('History');
	});

	test('page-2 link navigates normally from history page', async ({ page }) => {
		await page.click('a[href="/page-2.html"]');
		await expectToBeAt(page, '/page-2.html', 'Page 2');
	});
});
