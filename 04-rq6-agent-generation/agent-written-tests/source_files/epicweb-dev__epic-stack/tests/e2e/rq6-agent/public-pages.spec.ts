import { test, expect } from '@playwright/test'

test.describe('Marketing / Public Pages', () => {
	test('home page renders with title and logo grid', async ({ page }) => {
		await page.goto('/')
		await expect(page).toHaveTitle('Epic Notes')
		// Hero heading link to epic stack
		await expect(page.getByRole('heading', { name: 'The Epic Stack' })).toBeVisible()
		// Logo grid (tooltips/links)
		const logoGrid = page.getByRole('list').first()
		await expect(logoGrid).toBeVisible()
	})

	test('home page has nav with Log In button when anonymous', async ({ page }) => {
		await page.goto('/')
		await expect(page.getByRole('link', { name: 'Log In' })).toBeVisible()
	})

	test('home page footer has logo and theme switcher', async ({ page }) => {
		await page.goto('/')
		// Theme switch button exists (accessible name: Light, Dark, or System)
		const themeBtn = page.getByRole('button', { name: /light|dark|system/i })
		await expect(themeBtn).toBeVisible()
	})

	test('about page renders', async ({ page }) => {
		await page.goto('/about')
		await expect(page.getByText('About page')).toBeVisible()
	})

	test('privacy page renders', async ({ page }) => {
		await page.goto('/privacy')
		await expect(page.getByText('Privacy')).toBeVisible()
	})

	test('terms of service page renders', async ({ page }) => {
		await page.goto('/tos')
		await expect(page.getByText('Terms of service')).toBeVisible()
	})

	test('support page renders', async ({ page }) => {
		await page.goto('/support')
		await expect(page.getByText('Support')).toBeVisible()
	})

	test('404 page shows error for unknown route', async ({ page }) => {
		await page.goto('/this-page-does-not-exist-at-all-xyz123')
		// Shows "We can't find this page:"
		await expect(page.getByRole('heading', { name: /we can't find this page/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /back to home/i })).toBeVisible()
	})
})
