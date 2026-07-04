import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { expectToBeAt } from '../support/commands.js';

/**
 * Tests for the rapid-navigation fixture pages.
 *
 * These pages use Swup with cache:false and track received hook names via
 * window.data.received.  An aria-busy="true" attribute is set on <html>
 * during navigation and removed on visit:end.
 *
 * We focus on:
 *   1. Basic navigation still completes correctly between pages
 *   2. aria-busy is set during navigation and removed on completion
 *   3. Hook events are captured in window.data
 */
test.describe('rapid navigation: basic flow', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/rapid-navigation/page-1.html');
		await waitForSwup(page);
	});

	test('renders page 1 correctly', async ({ page }) => {
		await expect(page).toHaveTitle('Rapid Navigation Page 1');
		await expect(page.locator('h1')).toContainText('Rapid Navigation Page 1');
	});

	test('cache is disabled on rapid-navigation pages', async ({ page }) => {
		const cacheEnabled = await page.evaluate(() => window._swup.options.cache);
		expect(cacheEnabled).toBe(false);
	});

	test('navigates to page 2', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await expectToBeAt(page, '/rapid-navigation/page-2.html', 'Rapid Navigation Page 2');
	});

	test('navigates to page 3', async ({ page }) => {
		await page.click('[data-testid="link-to-page-3"]');
		await expectToBeAt(page, '/rapid-navigation/page-3.html', 'Rapid Navigation Page 3');
	});

	test('aria-busy is removed after navigation completes', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await page.waitForURL('/rapid-navigation/page-2.html');
		// aria-busy should be cleared once visit:end fires
		await expect(page.locator('html')).not.toHaveAttribute('aria-busy');
	});

	test('visit:start and visit:end hooks are captured in window.data', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await page.waitForURL('/rapid-navigation/page-2.html');
		// After navigation, wait for aria-busy to be absent (visit:end fired)
		await expect(page.locator('html')).not.toHaveAttribute('aria-busy');
		const received = await page.evaluate(() => window.data?.received);
		expect(Array.isArray(received)).toBe(true);
		expect(received).toContain('visit:start');
		expect(received).toContain('visit:end');
	});

	test('navigation sequence page-1 → 2 → 3 completes correctly', async ({ page }) => {
		await page.click('[data-testid="link-to-page-2"]');
		await expectToBeAt(page, '/rapid-navigation/page-2.html');
		await page.click('[data-testid="link-to-page-3"]');
		await expectToBeAt(page, '/rapid-navigation/page-3.html');
	});

	test('navigates back to page-1 after page-3', async ({ page }) => {
		await page.click('[data-testid="link-to-page-3"]');
		await page.waitForURL('/rapid-navigation/page-3.html');
		await page.click('[data-testid="link-to-page-1"]');
		await expectToBeAt(page, '/rapid-navigation/page-1.html', 'Rapid Navigation Page 1');
	});
});
