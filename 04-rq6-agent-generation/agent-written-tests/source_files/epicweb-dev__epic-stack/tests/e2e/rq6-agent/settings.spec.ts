import { test, expect, type Page } from '@playwright/test'

async function loginAsKody(page: Page) {
	await page.goto('/login')
	await page.getByLabel('Username').fill('kody')
	await page.getByLabel('Password').fill('kodylovesyou')
	await page.getByRole('button', { name: /log in/i }).click()
	await page.waitForURL(/^(?!.*\/login)/)
}

test.describe('Settings - Profile', () => {
	test('requires authentication to access settings', async ({ page }) => {
		await page.goto('/settings/profile')
		await expect(page).toHaveURL(/\/login/)
	})

	test('settings profile page renders for authenticated user', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')

		// Should show profile form
		await expect(page.getByLabel('Username')).toBeVisible()
		// Use exact: true to avoid matching "Username" label which contains "Name"
		await expect(page.getByLabel('Name', { exact: true })).toBeVisible()
		await expect(page.getByRole('button', { name: /save changes/i })).toBeVisible()
	})

	test('profile page shows current username', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		await expect(page.getByLabel('Username')).toHaveValue('kody')
	})

	test('profile page shows links to sub-sections', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')

		await expect(page.getByRole('link', { name: /change email/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /2fa|two.factor/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /password/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /connections/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /passkeys/i })).toBeVisible()
		await expect(page.getByRole('link', { name: /download/i })).toBeVisible()
	})

	test('profile page shows change photo button', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		await expect(page.getByRole('link', { name: /change profile photo/i })).toBeVisible()
	})

	test('shows session info', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		// Should show "this is your only session" or "sign out of other sessions"
		await expect(
			page.getByText(/only session|other sessions/i)
		).toBeVisible()
	})

	test('delete data button is present', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		await expect(page.getByRole('button', { name: /delete all your data/i })).toBeVisible()
	})

	test('delete data requires double confirmation', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		const deleteBtn = page.getByRole('button', { name: /delete all your data/i })
		await deleteBtn.click()
		// Should ask "are you sure?"
		await expect(page.getByRole('button', { name: /are you sure/i })).toBeVisible()
	})

	test('username validation shows error for empty username', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')

		// Clear username and submit - client-side Conform validation should fire
		await page.getByLabel('Username').clear()
		await page.getByRole('button', { name: /save changes/i }).click()
		await expect(page.getByText(/too short|required|minimum/i)).toBeVisible()
	})

	test('navigating to photo settings', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		await page.getByRole('link', { name: /change profile photo/i }).click()
		await expect(page).toHaveURL(/\/settings\/profile\/photo/)
	})

	test('navigating to password settings', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		await page.getByRole('link', { name: /change password/i }).click()
		await expect(page).toHaveURL(/\/settings\/profile\/password/)
	})

	test('navigating to change email', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile')
		await page.getByRole('link', { name: /change email/i }).click()
		await expect(page).toHaveURL(/\/settings\/profile\/change-email/)
	})
})

test.describe('Settings - Password', () => {
	test('password settings page renders', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile/password')
		await expect(page.getByLabel('Current Password')).toBeVisible()
		// Use exact: true to avoid "Confirm New Password" also matching "New Password"
		await expect(page.getByLabel('New Password', { exact: true })).toBeVisible()
		await expect(page.getByLabel('Confirm New Password')).toBeVisible()
		await expect(page.getByRole('button', { name: /change password/i })).toBeVisible()
	})

	test('shows error for incorrect current password', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile/password')
		await page.getByLabel('Current Password').fill('wrongpassword')
		// Use exact: true to avoid matching "Confirm New Password"
		await page.getByLabel('New Password', { exact: true }).fill('newpassword123')
		await page.getByLabel('Confirm New Password').fill('newpassword123')
		await page.getByRole('button', { name: /change password/i }).click()
		await expect(page.getByText(/incorrect password/i)).toBeVisible()
	})

	test('shows error when new passwords do not match', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile/password')
		await page.getByLabel('Current Password').fill('kodylovesyou')
		// Use exact: true to avoid matching "Confirm New Password"
		await page.getByLabel('New Password', { exact: true }).fill('newpassword123')
		await page.getByLabel('Confirm New Password').fill('differentpassword456')
		await page.getByRole('button', { name: /change password/i }).click()
		await expect(page.getByText(/must match/i)).toBeVisible()
	})

	test('cancel button returns to profile settings', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile/password')
		await page.getByRole('link', { name: /cancel/i }).click()
		await expect(page).toHaveURL(/\/settings\/profile$/)
	})
})

test.describe('Settings - Photo', () => {
	test('photo settings page renders', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile/photo')
		await expect(page).toHaveURL(/\/settings\/profile\/photo/)
		// Photo page shows user profile image and file input for uploading
		await expect(page.locator('img').first()).toBeVisible()
		// File input is present in DOM (it's visually hidden with sr-only class)
		await expect(page.locator('input[type="file"]')).toBeAttached()
	})
})

test.describe('Settings - Change Email', () => {
	test('change email page renders with form', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/settings/profile/change-email')
		await expect(page.getByLabel(/new email/i).or(page.getByLabel(/email/i))).toBeVisible()
	})
})
