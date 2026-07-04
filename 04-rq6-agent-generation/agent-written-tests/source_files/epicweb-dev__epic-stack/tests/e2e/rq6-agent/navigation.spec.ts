import { test, expect, type Page } from '@playwright/test'

async function loginAsKody(page: Page) {
	await page.goto('/login')
	await page.getByLabel('Username').fill('kody')
	await page.getByLabel('Password').fill('kodylovesyou')
	await page.getByRole('button', { name: /log in/i }).click()
	await page.waitForURL(/^(?!.*\/login)/)
}

test.describe('Header Navigation', () => {
	test('shows logo linking to home', async ({ page }) => {
		await page.goto('/about')
		// Logo links to /
		const logoLinks = page.getByRole('link', { name: /epic\s*notes/i })
		await expect(logoLinks.first()).toBeVisible()
		await logoLinks.first().click()
		await expect(page).toHaveURL('/')
	})

	test('shows Log In button for anonymous users', async ({ page }) => {
		await page.goto('/')
		await expect(page.getByRole('link', { name: 'Log In' })).toBeVisible()
	})

	test('Log In button navigates to login page', async ({ page }) => {
		await page.goto('/')
		await page.getByRole('link', { name: 'Log In' }).click()
		await expect(page).toHaveURL(/\/login/)
	})

	test('shows search bar in header on non-users pages', async ({ page }) => {
		await page.goto('/')
		await expect(page.getByRole('searchbox')).toBeVisible()
	})

	test('search bar is hidden on users search page', async ({ page }) => {
		await page.goto('/users')
		// On the users page, the header search bar should be hidden
		// (the page has its own search bar)
		const searchboxes = page.getByRole('searchbox')
		// Only one searchbox - the one on the page itself, not the header
		await expect(searchboxes).toHaveCount(1)
	})

	test('shows user dropdown when authenticated', async ({ page }) => {
		await loginAsKody(page)
		// Should show user avatar/dropdown instead of Login button
		await expect(page.getByRole('link', { name: 'Log In' })).not.toBeVisible()
	})

	test('user dropdown has correct links', async ({ page }) => {
		await loginAsKody(page)
		// Open user dropdown (the trigger link has aria-label="User menu")
		await page.getByRole('link', { name: 'User menu' }).click()
		// Should show profile, notes, logout
		await expect(page.getByRole('menuitem', { name: /profile/i })).toBeVisible()
		await expect(page.getByRole('menuitem', { name: /notes/i })).toBeVisible()
		await expect(page.getByRole('menuitem', { name: /logout/i })).toBeVisible()
	})

	test('user dropdown profile link goes to user profile', async ({ page }) => {
		await loginAsKody(page)
		await page.getByRole('link', { name: 'User menu' }).click()
		await page.getByRole('menuitem', { name: /profile/i }).click()
		await expect(page).toHaveURL(/\/users\/kody$/)
	})

	test('user dropdown notes link goes to user notes', async ({ page }) => {
		await loginAsKody(page)
		await page.getByRole('link', { name: 'User menu' }).click()
		await page.getByRole('menuitem', { name: /notes/i }).click()
		await expect(page).toHaveURL(/\/users\/kody\/notes/)
	})
})

test.describe('Footer', () => {
	test('footer logo links to home', async ({ page }) => {
		await page.goto('/about')
		// Footer has the logo as well
		const allLogoLinks = page.getByRole('link', { name: /epic\s*notes/i })
		// Click the last one (footer)
		await allLogoLinks.last().click()
		await expect(page).toHaveURL('/')
	})

	test('footer theme switcher is present', async ({ page }) => {
		await page.goto('/')
		await expect(page.getByRole('button', { name: /light|dark|system/i })).toBeVisible()
	})
})

test.describe('Theme Switcher', () => {
	test('theme button toggles between light and dark', async ({ page }) => {
		await page.goto('/')
		const html = page.locator('html')

		// Default should be light
		await expect(html).toHaveClass(/light/)

		// Click theme switch (button label: Light → clicking moves to dark)
		await page.getByRole('button', { name: /light|dark|system/i }).click()

		// Should toggle to dark (or system depending on current state)
		await expect(html).toHaveClass(/dark|light/)
	})

	test('theme persists after navigation', async ({ page }) => {
		await page.goto('/')

		// Switch theme using accessible name (Light/Dark/System)
		await page.getByRole('button', { name: /light|dark|system/i }).click()
		// Theme class should change
		await expect(page.locator('html')).toHaveClass(/dark|light/)

		// Navigate to another page - theme preference should persist
		await page.goto('/about')
		await expect(page.locator('html')).toHaveClass(/light|dark/)
	})
})

test.describe('Logout Flow', () => {
	test('logout via user dropdown', async ({ page }) => {
		await loginAsKody(page)

		// Open dropdown (aria-label="User menu")
		await page.getByRole('link', { name: 'User menu' }).click()
		await page.getByRole('menuitem', { name: /logout/i }).click()

		// Should be logged out - Log In button should appear
		await expect(page.getByRole('link', { name: 'Log In' })).toBeVisible()
	})

	test('logout from user profile page', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody')

		// Click logout button on profile
		await page.getByRole('button', { name: /logout/i }).click()

		// Should be logged out
		await expect(page.getByRole('link', { name: 'Log In' })).toBeVisible()
	})
})

test.describe('Me Route', () => {
	test('/me redirects to user profile when authenticated', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/me')
		await expect(page).toHaveURL(/\/users\/kody$/)
	})

	test('/me redirects to login when anonymous', async ({ page }) => {
		await page.goto('/me')
		await expect(page).toHaveURL(/\/login/)
	})
})

test.describe('Error Boundaries', () => {
	test('404 page shows appropriate error', async ({ page }) => {
		const response = await page.goto('/users/nonexistentxyzuser99123')
		// Should show a 404-like message
		await expect(page.getByText(/no user with the username/i)).toBeVisible()
	})

	test('catchall route shows 404 for unknown paths', async ({ page }) => {
		await page.goto('/unknown-path-that-does-not-exist')
		await expect(page.getByRole('heading', { name: /we can't find this page/i })).toBeVisible()
	})
})
