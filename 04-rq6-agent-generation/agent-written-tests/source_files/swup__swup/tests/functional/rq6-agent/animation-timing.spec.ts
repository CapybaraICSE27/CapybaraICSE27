import { test, expect } from '@playwright/test';

import { waitForSwup, expectSwupAnimationDuration } from '../support/swup.js';

/**
 * Tests for CSS animation duration measurement on the three timing fixture pages:
 * - /animation-duration.html   — 0.4 s opacity transition (400 ms out + in)
 * - /animation-complex.html    — two properties, max combined = 600 ms
 * - /animation-keyframes.html  — keyframe with 300 ms delay + 400 ms duration = 700 ms
 */

test.describe('animation timing: duration (0.4s)', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/animation-duration.html');
		await waitForSwup(page);
	});

	test('renders correct heading', async ({ page }) => {
		await expect(page.locator('h1')).toContainText('Animation duration');
	});

	test('measures 400 ms out and in animation', async ({ page }) => {
		await expectSwupAnimationDuration(page, { out: 400, in: 400, total: 800 });
	});

	test('nav links cover all animation pages', async ({ page }) => {
		const links = page.locator('.header a');
		const count = await links.count();
		expect(count).toBeGreaterThanOrEqual(5);
	});
});

test.describe('animation timing: complex (max 600 ms)', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/animation-complex.html');
		await waitForSwup(page);
	});

	test('renders correct heading', async ({ page }) => {
		await expect(page.locator('h1')).toContainText('Animation duration: complex');
	});

	test('measures 600 ms out and in animation (max of opacity+delay vs transform+delay)', async ({ page }) => {
		// opacity 100ms 200ms → ends at 300ms; transform 400ms 200ms → ends at 600ms
		await expectSwupAnimationDuration(page, { out: 600, in: 600, total: 1200 });
	});
});

test.describe('animation timing: keyframes (700 ms)', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/animation-keyframes.html');
		await waitForSwup(page);
	});

	test('renders correct heading', async ({ page }) => {
		await expect(page.locator('h1')).toContainText('Animation duration: keyframes');
	});

	test('measures 700 ms out and in animation (400 ms + 300 ms delay)', async ({ page }) => {
		await expectSwupAnimationDuration(page, { out: 700, in: 700, total: 1400 });
	});
});
