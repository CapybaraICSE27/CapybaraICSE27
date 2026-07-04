import { expect, test } from '@playwright/test'
import { setupRouteMocks } from './fixtures'

/**
 * Tests that each example category has at least one representative example
 * that loads successfully (sidebar visible, active sidebar item highlighted).
 *
 * NOTE: Because the running Vite dev server has a cached "file not found" result
 * for `tldraw/tldraw.css`, all example components are intercepted and replaced with
 * minimal stub modules (returning null).  This means the tldraw canvas is NOT
 * rendered in these tests.  What IS reliably testable is:
 *   - The ExamplePage shell (sidebar + content wrapper) renders
 *   - The correct sidebar item is marked active
 *   - The URL reflects the navigated example
 */

/** Checks that a single-editor example page loads its shell correctly */
async function expectExampleLoads(page: any, path: string) {
	await setupRouteMocks(page)
	await page.goto(path)
	// Sidebar must be rendered
	await expect(page.locator('nav.example__sidebar')).toBeVisible({ timeout: 15_000 })
	// Main content area must be rendered
	await expect(page.locator('.example__content')).toBeVisible()
	// The active sidebar item should be highlighted for the current page
	const activeItem = page.locator(`.examples__sidebar__item[data-active="true"]`)
	await expect(activeItem).toBeVisible()
}

test.describe('Getting started', () => {
	test('/basic loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/basic')
	})
})

test.describe('Configuration examples', () => {
	test('/readonly loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/readonly')
	})

	test('/only-editor loads sidebar shell', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/only-editor')
		await expect(page.locator('nav.example__sidebar')).toBeVisible({ timeout: 15_000 })
		await expect(page.locator('.example__content')).toBeVisible()
	})

	test('/persistence-key loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/persistence-key')
	})

	test('/camera-options loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/camera-options')
	})

	test('/display-options loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/display-options')
	})

	test('/disable-pages loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/disable-pages')
	})

	test('/reduced-motion loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/reduced-motion')
	})
})

test.describe('Editor API examples', () => {
	test('/api loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/api')
	})

	test('/snapshots loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/snapshots')
	})

	test('/focus-mode loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/focus-mode')
	})

	test('/z-order loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/z-order')
	})

	test('/locked-shapes loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/locked-shapes')
	})

	test('/zoom-to-bounds loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/zoom-to-bounds')
	})

	test('/text-search loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/text-search')
	})
})

test.describe('UI & theming examples', () => {
	test('/dark-mode loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/dark-mode')
	})

	test('/custom-ui loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/custom-ui')
	})

	test('/keyboard-shortcuts loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/keyboard-shortcuts')
	})

	test('/custom-theme loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/custom-theme')
	})

	test('/hide-ui loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/hide-ui')
	})

	test('/dark-mode-toggle loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/dark-mode-toggle')
	})
})

test.describe('Page layout examples', () => {
	test('/inline loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/inline')
	})

	test('/multiple loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/multiple')
	})

	test('/scroll loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/scroll')
	})

	test('/inset loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/inset')
	})
})

test.describe('Events & effects examples', () => {
	test('/canvas-events loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/canvas-events')
	})

	test('/store-events loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/store-events')
	})

	test('/ui-events loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/ui-events')
	})

	test('/permissions loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/permissions')
	})
})

test.describe('Shapes & tools examples', () => {
	test('/custom-shape loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/custom-shape')
	})

	test('/custom-tool loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/custom-tool')
	})

	test('/speech-bubble loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/speech-bubble')
	})

	test('/drag-and-drop loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/drag-and-drop')
	})
})

test.describe('Users examples', () => {
	test('/custom-user loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/custom-user')
	})

	test('/attribution loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/attribution')
	})
})

test.describe('Use cases examples', () => {
	test('/slides loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/slides')
	})

	test('/snowstorm loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/snowstorm')
	})

	test('/image-annotator loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/image-annotator')
	})
})

test.describe('Data & assets examples', () => {
	test('/export-canvas-as-image loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/export-canvas-as-image')
	})

	test('/local-storage loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/local-storage')
	})

	test('/static-assets loads sidebar shell', async ({ page }) => {
		await expectExampleLoads(page, '/static-assets')
	})
})

test.describe('Collaboration examples', () => {
	test('/sync-demo loads sidebar shell', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/sync-demo')
		await expect(page.locator('nav.example__sidebar')).toBeVisible({ timeout: 15_000 })
		await expect(page.locator('.example__content')).toBeVisible()
		// Active item in sidebar
		await expect(page.locator(`.examples__sidebar__item[data-active="true"]`)).toBeVisible()
	})

	test('/user-presence loads sidebar shell', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/user-presence')
		await expect(page.locator('nav.example__sidebar')).toBeVisible({ timeout: 15_000 })
		await expect(page.locator('.example__content')).toBeVisible()
		await expect(page.locator(`.examples__sidebar__item[data-active="true"]`)).toBeVisible()
	})
})
