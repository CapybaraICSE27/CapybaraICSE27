import { test, expect } from '@playwright/test';

import { waitForSwup, navigateWithSwup } from '../support/swup.js';
import { clickOnLink, expectToBeAt } from '../support/commands.js';

/**
 * Tests for the HTML element's animation class lifecycle during a Swup navigation.
 *
 * Expected class sequence:
 *   visit:start          → is-changing added
 *   animation:out:start  → is-animating, is-leaving added
 *   animation:out:end    → is-leaving removed
 *   content replaced     → is-rendering added
 *   animation:in:end     → is-animating, is-rendering removed
 *   visit:end            → is-changing removed
 */
test.describe('animation classes: duration page', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/animation-duration.html');
		await waitForSwup(page);
	});

	test('is-changing is set during navigation', async ({ page }) => {
		const hadIsChanging = await page.evaluate(() => {
			return new Promise<boolean>((resolve) => {
				window._swup.hooks.on('animation:out:start', () => {
					resolve(document.documentElement.classList.contains('is-changing'));
				});
				window._swup.navigate(window.location.href);
			});
		});
		expect(hadIsChanging).toBe(true);
	});

	test('is-animating is set during out animation', async ({ page }) => {
		const hadIsAnimating = await page.evaluate(() => {
			return new Promise<boolean>((resolve) => {
				window._swup.hooks.on('animation:out:start', () => {
					resolve(document.documentElement.classList.contains('is-animating'));
				});
				window._swup.navigate(window.location.href);
			});
		});
		expect(hadIsAnimating).toBe(true);
	});

	test('is-leaving is set during out animation', async ({ page }) => {
		const hadIsLeaving = await page.evaluate(() => {
			return new Promise<boolean>((resolve) => {
				window._swup.hooks.on('animation:out:start', () => {
					resolve(document.documentElement.classList.contains('is-leaving'));
				});
				window._swup.navigate(window.location.href);
			});
		});
		expect(hadIsLeaving).toBe(true);
	});

	test('all animation classes are removed after navigation completes', async ({ page }) => {
		await navigateWithSwup(page, '/animation-complex.html');
		await page.waitForSelector('html:not(.is-changing)');
		const html = page.locator('html');
		await expect(html).not.toHaveClass(/is-changing/);
		await expect(html).not.toHaveClass(/is-animating/);
		await expect(html).not.toHaveClass(/is-leaving/);
		await expect(html).not.toHaveClass(/is-rendering/);
	});

	test('animation hooks fire in correct order', async ({ page }) => {
		const order = await page.evaluate(() => {
			return new Promise<string[]>((resolve) => {
				const events: string[] = [];
				const record = (name: string) => events.push(name);
				window._swup.hooks.on('animation:out:start', () => record('out:start'));
				window._swup.hooks.on('animation:out:end',   () => record('out:end'));
				window._swup.hooks.on('animation:in:start',  () => record('in:start'));
				window._swup.hooks.on('animation:in:end',    () => record('in:end'));
				window._swup.hooks.on('visit:end', () => resolve(events));
				window._swup.navigate(window.location.href);
			});
		});
		expect(order.indexOf('out:start')).toBeLessThan(order.indexOf('out:end'));
		expect(order.indexOf('out:end')).toBeLessThan(order.indexOf('in:start'));
		expect(order.indexOf('in:start')).toBeLessThan(order.indexOf('in:end'));
	});
});

test.describe('animation classes: navigation between pages', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/animation-duration.html');
		await waitForSwup(page);
	});

	test('navigates between animation pages and cleans up classes', async ({ page }) => {
		await clickOnLink(page, '/animation-keyframes.html');
		await expectToBeAt(page, '/animation-keyframes.html');
		await page.waitForSelector('html:not(.is-changing)');
		const html = page.locator('html');
		await expect(html).not.toHaveClass(/is-changing/);
		await expect(html).not.toHaveClass(/is-animating/);
	});

	test('multiple navigations clean up classes each time', async ({ page }) => {
		for (const url of ['/animation-complex.html', '/animation-keyframes.html', '/animation-duration.html']) {
			await navigateWithSwup(page, url);
			await page.waitForSelector('html:not(.is-changing)');
			const html = page.locator('html');
			await expect(html).not.toHaveClass(/is-changing/);
			await expect(html).not.toHaveClass(/is-animating/);
		}
	});
});
