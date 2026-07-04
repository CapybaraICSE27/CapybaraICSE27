import { expect, test } from '@playwright/test'
import { setupRouteMocks } from './fixtures'

/**
 * Tests for special pages: /develop, /end-to-end, and the 404 handler.
 *
 * NOTE: /develop and /end-to-end are standalone pages (no ExamplePage sidebar
 * wrapper) whose components import `tldraw/tldraw.css`.  Since the running Vite
 * dev server has a stale cache for that file, the components are intercepted by
 * setupRouteMocks and replaced with minimal stubs (returning null).  These tests
 * therefore verify that the *routing* works correctly (no crash, correct URL) rather
 * than asserting on canvas content.
 */

test.describe('Special pages', () => {
	test('/develop page loads without application error', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/develop')
		// Page should load and navigate to /develop
		await expect(page).toHaveURL(/\/develop/)
		// No React error boundary crash
		await expect(page.locator('body')).not.toContainText('Unexpected Application Error')
		// The root element exists and is attached
		await expect(page.locator('#root')).toBeAttached()
	})

	test('/end-to-end page loads without application error', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/end-to-end')
		await expect(page).toHaveURL(/\/end-to-end/)
		await expect(page.locator('body')).not.toContainText('Unexpected Application Error')
		await expect(page.locator('#root')).toBeAttached()
	})

	test('404 page shown for unknown route', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/this-path-absolutely-does-not-exist-xyz')
		await expect(page.locator('body')).toContainText('404')
	})
})
