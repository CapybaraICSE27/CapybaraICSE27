import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { expectToBeAt, expectNoPageReload, expectPageReload } from '../support/commands.js';

/**
 * Tests for ignore-visit behaviour on /ignore-visits.html.
 *
 * Swup respects the `data-no-swup` attribute:
 *   - On the link itself           → causes a full browser reload
 *   - On a parent element          → causes a full browser reload
 *   - Normal link (no attribute)   → standard Swup navigation (no reload)
 */
test.describe('ignore visits: data-no-swup', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/ignore-visits.html');
		await waitForSwup(page);
	});

	test('renders ignore-visits page correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Ignore visits');
		await expect(page.locator('h1')).toContainText('Ignore visits');
	});

	test('normal link navigates via Swup (no full reload)', async ({ page }) => {
		await expectNoPageReload(page, async () => {
			await page.click('[data-testid="ignore-none"]');
			await page.waitForURL('/page-2.html');
		});
		await expectToBeAt(page, '/page-2.html');
	});

	test('link with data-no-swup causes a full page reload', async ({ page }) => {
		await expectPageReload(page, async () => {
			await page.click('[data-testid="ignore-element"]');
			await page.waitForURL('/page-2.html');
		});
	});

	test('link whose parent has data-no-swup causes a full page reload', async ({ page }) => {
		await expectPageReload(page, async () => {
			await page.click('[data-testid="ignore-parent"]');
			await page.waitForURL('/page-2.html');
		});
	});
});
