import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { clickOnLink, expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for data-swup-persist — elements with matching persist keys are
 * kept in place across navigations instead of being replaced.
 *
 * persist-1.html and persist-2.html both have:
 *   <p data-testid="unpersisted">Persist N</p>
 *   <p data-testid="persisted"   data-swup-persist="paragraph">Persist N</p>
 *
 * After navigating 1 → 2 the persisted paragraph should retain the text from
 * page-1 while the unpersisted paragraph updates to page-2's text.
 */
test.describe('persist: data-swup-persist', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/persist-1.html');
		await waitForSwup(page);
	});

	test('renders correct initial content on page 1', async ({ page }) => {
		await expect(page.locator('[data-testid="unpersisted"]')).toContainText('Persist 1');
		await expect(page.locator('[data-testid="persisted"]')).toContainText('Persist 1');
	});

	test('navigates to page 2 without full reload', async ({ page }) => {
		await expectNoPageReload(page, () => clickOnLink(page, '/persist-2.html'));
		await expectToBeAt(page, '/persist-2.html');
	});

	test('unpersisted element text is updated after navigation', async ({ page }) => {
		await clickOnLink(page, '/persist-2.html');
		await expectToBeAt(page, '/persist-2.html');
		await expect(page.locator('[data-testid="unpersisted"]')).toContainText('Persist 2');
	});

	test('persisted element keeps page-1 text after navigation to page-2', async ({ page }) => {
		await clickOnLink(page, '/persist-2.html');
		await expectToBeAt(page, '/persist-2.html');
		// The persisted element should still show "Persist 1" (kept from page 1)
		await expect(page.locator('[data-testid="persisted"]')).toContainText('Persist 1');
	});

	test('navigating back to page 1 updates unpersisted element', async ({ page }) => {
		await clickOnLink(page, '/persist-2.html');
		await clickOnLink(page, '/persist-1.html');
		await expectToBeAt(page, '/persist-1.html');
		await expect(page.locator('[data-testid="unpersisted"]')).toContainText('Persist 1');
	});

	test('page 2 standalone renders correct content', async ({ page }) => {
		await navigateWithSwup(page, '/persist-2.html');
		await expect(page.locator('h1')).toContainText('Persist 2');
	});
});
