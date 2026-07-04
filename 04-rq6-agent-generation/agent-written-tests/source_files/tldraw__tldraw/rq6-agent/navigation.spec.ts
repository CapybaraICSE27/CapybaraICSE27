import { expect, test } from '@playwright/test'
import { setupRouteMocks } from './fixtures'

/**
 * Tests for the sidebar navigation, search, logo, and overall page structure
 * of the tldraw examples app.
 *
 * NOTE: The running Vite dev server has a module-resolution cache issue for
 * `tldraw/tldraw.css`.  Each test calls `setupRouteMocks(page)` which
 * intercepts the failing 500 responses and substitutes minimal stubs so
 * the rest of the page (sidebar, dialogs, etc.) renders normally.
 */

test.describe('App shell & navigation', () => {
	test('homepage loads the basic example with sidebar', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		await expect(page.locator('nav.example__sidebar')).toBeVisible()
		await expect(page.locator('.example__content')).toBeVisible()
	})

	test('sidebar logo link is visible and labelled correctly', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		// The sidebar logo link has accessible name "tldraw examples"
		const logoLink = page.getByRole('link', { name: 'tldraw examples' })
		await expect(logoLink).toBeVisible()
		// Logo link is in the sidebar header area
		await expect(logoLink).toBeAttached()
	})

	test('sidebar contains all category headers', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		await expect(page.getByText('Getting started')).toBeVisible()
		await expect(page.getByText('Configuration')).toBeVisible()
		await expect(page.getByText('Editor API')).toBeVisible()
		await expect(page.getByText('UI & theming')).toBeVisible()
		await expect(page.getByText('Page layout')).toBeVisible()
		await expect(page.getByText('Events & effects')).toBeVisible()
		await expect(page.getByText('Shapes & tools')).toBeVisible()
		await expect(page.getByText('Users')).toBeVisible()
		await expect(page.getByText('Collaboration')).toBeVisible()
		await expect(page.getByText('Data & assets')).toBeVisible()
		await expect(page.getByText('Use cases')).toBeVisible()
	})

	test('sidebar has example list items', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		const items = await page.locator('.examples__sidebar__item__link').count()
		expect(items).toBeGreaterThan(50)
	})

	test('sidebar search input is present and labelled', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		const searchInput = page.getByRole('textbox', { name: 'Search examples' })
		await expect(searchInput).toBeVisible()
	})

	test('sidebar search filters examples by keyword', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		const searchInput = page.getByRole('textbox', { name: 'Search examples' })
		const initialCount = await page.locator('.examples__sidebar__item__link').count()
		await searchInput.fill('dark')
		const filteredCount = await page.locator('.examples__sidebar__item__link').count()
		expect(filteredCount).toBeGreaterThan(0)
		expect(filteredCount).toBeLessThan(initialCount)
	})

	test('sidebar search shows matching titles', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		await page.getByRole('textbox', { name: 'Search examples' }).fill('dark')
		const titles = await page.locator('.examples__sidebar__item__title').allTextContents()
		expect(titles.length).toBeGreaterThan(0)
		// At least one of the returned titles should contain "dark"
		const hasDarkTitle = titles.some((t) => t.toLowerCase().includes('dark'))
		expect(hasDarkTitle).toBe(true)
	})

	test('sidebar search cleared shows all examples', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		const searchInput = page.getByRole('textbox', { name: 'Search examples' })
		await searchInput.fill('dark')
		const filteredCount = await page.locator('.examples__sidebar__item__link').count()
		await searchInput.fill('')
		const clearedCount = await page.locator('.examples__sidebar__item__link').count()
		expect(clearedCount).toBeGreaterThan(filteredCount)
	})

	test('logo link navigates to root from another example page', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/dark-mode')
		await expect(page).toHaveURL(/\/dark-mode/)
		await page.getByRole('link', { name: 'tldraw examples' }).click()
		await expect(page).toHaveURL(/\/$/)
	})

	test('clicking a sidebar example link navigates to that example', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		const darkModeLink = page.locator('a.examples__sidebar__item__link[href*="dark-mode"]').first()
		await darkModeLink.click()
		await expect(page).toHaveURL(/dark-mode/)
	})

	test('navigated example shows as active in sidebar', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/dark-mode')
		const activeItem = page.locator('.examples__sidebar__item[data-active="true"]')
		await expect(activeItem).toBeVisible()
		const activeLink = activeItem.locator('.examples__sidebar__item__link')
		const href = await activeLink.getAttribute('href')
		expect(href).toContain('dark-mode')
	})

	test('active example shows info and standalone buttons', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await expect(page.getByRole('button', { name: 'Info' })).toBeVisible()
		await expect(page.getByRole('link', { name: 'Standalone' })).toBeVisible()
	})

	test('info dialog opens when clicking Info button', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await page.getByRole('button', { name: 'Info' }).click()
		await expect(page.getByRole('alertdialog')).toBeVisible()
	})

	test('info dialog shows a title', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await page.getByRole('button', { name: 'Info' }).click()
		await expect(page.getByRole('alertdialog')).toBeVisible()
		// The dialog title should contain some text
		const title = page.locator('.example__dialog__title')
		await expect(title).toBeVisible()
		const text = await title.textContent()
		expect(text?.length).toBeGreaterThan(0)
	})

	test('info dialog closes via Close button', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await page.getByRole('button', { name: 'Info' }).click()
		await expect(page.getByRole('alertdialog')).toBeVisible()
		await page.locator('.example__dialog__close').click()
		await expect(page.getByRole('alertdialog')).not.toBeVisible()
	})

	test('info dialog closes via Escape key', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await page.getByRole('button', { name: 'Info' }).click()
		await expect(page.getByRole('alertdialog')).toBeVisible()
		// Radix UI dialogs close when Escape is pressed (standard keyboard dismissal)
		await page.keyboard.press('Escape')
		await expect(page.getByRole('alertdialog')).not.toBeVisible()
	})

	test('info dialog has View Source link', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await page.getByRole('button', { name: 'Info' }).click()
		await expect(page.getByRole('alertdialog')).toBeVisible()
		// The dialog actions include a "View Source" link
		const viewSource = page.locator('.example__dialog__actions a')
		await expect(viewSource).toBeVisible()
		const href = await viewSource.getAttribute('href')
		expect(href).toContain('github.com')
	})

	test('standalone view hides the sidebar', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic/full')
		// In standalone view there is no sidebar
		await expect(page.locator('nav.example__sidebar')).not.toBeVisible()
		// The page should load without a full-page error (no error heading)
		await expect(page.locator('body')).not.toContainText('Unexpected Application Error')
	})

	test('collapse sidebar button navigates to full view', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/basic')
		await page.getByRole('link', { name: 'Collapse sidebar' }).click()
		await expect(page).toHaveURL(/\/basic\/full/)
	})

	test('sidebar footer links are present', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		await expect(
			page.locator('.example__sidebar__footer-link').filter({ hasText: 'Build with' })
		).toBeVisible()
		await expect(
			page.locator('.example__sidebar__footer-link').filter({ hasText: 'Request an example' })
		).toBeVisible()
		await expect(
			page.locator('.example__sidebar__footer-link').filter({ hasText: 'Visit the docs' })
		).toBeVisible()
	})

	test('Develop action link is present in sidebar', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		const devLink = page.locator('a.example__sidebar__action-row[href="/develop"]')
		await expect(devLink).toBeVisible()
	})

	test('404 page for unknown route', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/this-route-does-not-exist-at-all')
		await expect(page.locator('body')).toContainText('404')
	})

	test('URL search param ?filter pre-fills search box', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/?filter=dark')
		const searchInput = page.getByRole('textbox', { name: 'Search examples' })
		await expect(searchInput).toHaveValue('dark')
		const items = await page.locator('.examples__sidebar__item__link').count()
		expect(items).toBeGreaterThan(0)
	})

	test('URL updates when example is changed via search and click', async ({ page }) => {
		await setupRouteMocks(page)
		await page.goto('/')
		await page.getByRole('textbox', { name: 'Search examples' }).fill('slides')
		const slidesLink = page.locator('a.examples__sidebar__item__link[href*="slides"]').first()
		await slidesLink.click()
		await expect(page).toHaveURL(/slides/)
	})
})
