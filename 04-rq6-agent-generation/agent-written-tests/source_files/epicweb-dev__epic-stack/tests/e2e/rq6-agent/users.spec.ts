import { test, expect } from '@playwright/test'

test.describe('Users Search Page', () => {
	test('renders users page with search bar and title', async ({ page }) => {
		await page.goto('/users')
		await expect(page.getByRole('heading', { name: /epic notes users/i })).toBeVisible()
		await expect(page.getByRole('searchbox')).toBeVisible()
	})

	test('shows users in the list', async ({ page }) => {
		await page.goto('/users')
		// Should show some users (seeded data)
		const userLinks = page.getByRole('link').filter({ hasText: /profile/ })
		// At least one user should exist
		await expect(page.locator('ul li').first()).toBeVisible()
	})

	test('search filters users by username', async ({ page }) => {
		await page.goto('/users')
		await page.getByRole('searchbox').fill('kody')
		// Wait for search to complete (debounced)
		await page.waitForTimeout(600)
		await expect(page.getByRole('link', { name: /kody/i })).toBeVisible()
	})

	test('search shows no users found for non-existent user', async ({ page }) => {
		// Navigate directly with search param for reliability
		await page.goto('/users?search=zzznobodyxyz99999')
		await expect(page.getByText(/no users found/i)).toBeVisible()
	})

	test('navigates to user profile when clicking user card', async ({ page }) => {
		await page.goto('/users?search=kody')
		await page.waitForTimeout(600)
		await page.getByRole('link', { name: /kody/i }).click()
		await expect(page).toHaveURL(/\/users\/kody/)
	})

	test('search via URL param works', async ({ page }) => {
		await page.goto('/users?search=kody')
		await expect(page.getByRole('link', { name: /kody/i })).toBeVisible()
	})

	test('header search bar exists on non-users page', async ({ page }) => {
		await page.goto('/')
		// Search bar should be visible in header (not on users page)
		await expect(page.getByRole('searchbox')).toBeVisible()
	})

	test('searching from header navigates to users page', async ({ page }) => {
		await page.goto('/')
		await page.getByRole('searchbox').fill('kody')
		await page.getByRole('searchbox').press('Enter')
		await expect(page).toHaveURL(/\/users.*search=kody/)
	})
})

test.describe('User Profile Page', () => {
	test('renders kody profile page', async ({ page }) => {
		await page.goto('/users/kody')
		await expect(page).toHaveTitle(/kody.*epic notes/i)
		// Should show display name
		await expect(page.getByRole('heading', { name: /kody/i })).toBeVisible()
		// Should show joined date
		await expect(page.getByText(/joined/i)).toBeVisible()
	})

	test('shows notes link for kody profile', async ({ page }) => {
		await page.goto('/users/kody')
		// The button says "Kody's notes" for anonymous users
		await expect(page.getByRole('link', { name: /kody's notes/i })).toBeVisible()
	})

	test('clicking notes link navigates to notes', async ({ page }) => {
		await page.goto('/users/kody')
		await page.getByRole('link', { name: /kody's notes/i }).click()
		await expect(page).toHaveURL(/\/users\/kody\/notes/)
	})

	test('404 for non-existent user', async ({ page }) => {
		await page.goto('/users/nonexistentuser99xyz')
		await expect(page.getByText(/no user with the username/i)).toBeVisible()
	})

	test('profile shows avatar image', async ({ page }) => {
		await page.goto('/users/kody')
		// Should have an image (avatar)
		await expect(page.locator('img').first()).toBeVisible()
	})

	test('shows logout button when viewing own profile (authenticated)', async ({ page }) => {
		// Login first
		await page.goto('/login')
		await page.getByLabel('Username').fill('kody')
		await page.getByLabel('Password').fill('kodylovesyou')
		await page.getByRole('button', { name: /log in/i }).click()
		await page.waitForURL(/^(?!.*\/login)/)

		// Navigate to kody's profile
		await page.goto('/users/kody')
		await expect(page.getByRole('button', { name: /logout/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /my notes/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /edit profile/i })).toBeVisible()
	})
})

test.describe('Notes Layout', () => {
	test('renders notes layout with sidebar', async ({ page }) => {
		await page.goto('/users/kody/notes')
		// Notes layout title
		await expect(page.getByRole('heading', { name: /kody.*notes/i })).toBeVisible()
		// Should show "Select a note" in main area
		await expect(page.getByText(/select a note/i)).toBeVisible()
	})

	test('shows notes in sidebar', async ({ page }) => {
		await page.goto('/users/kody/notes')
		// Notes should appear in the sidebar (seeded with specific titles)
		await expect(page.getByRole('link', { name: /basic koala facts/i })).toBeVisible()
	})

	test('navigates to note when clicked', async ({ page }) => {
		await page.goto('/users/kody/notes')
		await page.getByRole('link', { name: /basic koala facts/i }).click()
		await expect(page).toHaveURL(/\/users\/kody\/notes\/d27a197e/)
	})

	test('shows individual note content', async ({ page }) => {
		await page.goto('/users/kody/notes/d27a197e')
		await expect(page.getByRole('heading', { name: /basic koala facts/i })).toBeVisible()
		await expect(page.getByText(/eucalyptus forests/i)).toBeVisible()
	})

	test('shows note timestamp when authenticated as owner', async ({ page }) => {
		// Login first - the toolbar (with timestamp) only shows for owner/can-delete
		await page.goto('/login')
		await page.getByLabel('Username').fill('kody')
		await page.getByLabel('Password').fill('kodylovesyou')
		await page.getByRole('button', { name: /log in/i }).click()
		await page.waitForURL(/^(?!.*\/login)/)

		await page.goto('/users/kody/notes/d27a197e')
		// Should show "X ago" timestamp (e.g., "5 months ago")
		await expect(page.getByText(/\d+ \w+ ago|about .* ago|\w+ ago/i)).toBeVisible()
	})

	test('404 for non-existent note', async ({ page }) => {
		await page.goto('/users/kody/notes/nonexistentnote99xyz')
		await expect(page.getByText(/no note with the id/i)).toBeVisible()
	})

	test('shows new note link for authenticated owner', async ({ page }) => {
		// Login as kody
		await page.goto('/login')
		await page.getByLabel('Username').fill('kody')
		await page.getByLabel('Password').fill('kodylovesyou')
		await page.getByRole('button', { name: /log in/i }).click()
		await page.waitForURL(/^(?!.*\/login)/)

		await page.goto('/users/kody/notes')
		await expect(page.getByRole('link', { name: /new note/i })).toBeVisible()
	})
})
