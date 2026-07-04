import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { clickOnLink, expectToBeAt, expectNoPageReload } from '../support/commands.js';

/**
 * Tests for multiple-container navigation.
 *
 * containers-1.html and containers-2.html use containers: ['#main', '#aside'].
 * On navigation both #main and #aside are replaced.
 */
test.describe('containers: multiple containers', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/containers-1.html');
		await waitForSwup(page);
	});

	test('renders page 1 content in both containers', async ({ page }) => {
		await expect(page.locator('#main h1')).toContainText('Containers 1');
		await expect(page.locator('#aside h2')).toContainText('Heading 1');
	});

	test('swup is configured with two containers', async ({ page }) => {
		const containers = await page.evaluate(() => window._swup.options.containers);
		expect(containers).toEqual(['#main', '#aside']);
	});

	test('navigates to page 2 without full reload', async ({ page }) => {
		await expectNoPageReload(page, () => clickOnLink(page, '/containers-2.html'));
		await expectToBeAt(page, '/containers-2.html');
	});

	test('#main content is replaced on navigation', async ({ page }) => {
		await clickOnLink(page, '/containers-2.html');
		await expect(page.locator('#main h1')).toContainText('Containers 2');
	});

	test('#aside content is replaced on navigation', async ({ page }) => {
		await clickOnLink(page, '/containers-2.html');
		await expect(page.locator('#aside h2')).toContainText('Heading 2');
	});

	test('both containers update simultaneously', async ({ page }) => {
		await clickOnLink(page, '/containers-2.html');
		await expect(page.locator('#main h1')).toContainText('Containers 2');
		await expect(page.locator('#aside h2')).toContainText('Heading 2');
	});

	test('can navigate back to page 1 from page 2', async ({ page }) => {
		await clickOnLink(page, '/containers-2.html');
		await clickOnLink(page, '/containers-1.html');
		await expect(page.locator('#main h1')).toContainText('Containers 1');
		await expect(page.locator('#aside h2')).toContainText('Heading 1');
	});

	test('document title updates on navigation', async ({ page }) => {
		await clickOnLink(page, '/containers-2.html');
		await expect(page).toHaveTitle('Containers 2');
	});

	test('navigates via API and updates both containers', async ({ page }) => {
		await navigateWithSwup(page, '/containers-2.html');
		await expect(page.locator('#main h1')).toContainText('Containers 2');
		await expect(page.locator('#aside h2')).toContainText('Heading 2');
	});
});
