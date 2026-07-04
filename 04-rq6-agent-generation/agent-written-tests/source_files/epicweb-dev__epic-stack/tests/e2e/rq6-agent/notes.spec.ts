import { test, expect, type Page } from '@playwright/test'

async function loginAsKody(page: Page) {
	await page.goto('/login')
	await page.getByLabel('Username').fill('kody')
	await page.getByLabel('Password').fill('kodylovesyou')
	await page.getByRole('button', { name: /log in/i }).click()
	await page.waitForURL(/^(?!.*\/login)/)
}

test.describe('Note View', () => {
	test('renders note with title and content', async ({ page }) => {
		await page.goto('/users/kody/notes/d27a197e')
		await expect(page.getByRole('heading', { name: /basic koala facts/i })).toBeVisible()
		await expect(page.getByText(/eucalyptus forests/i)).toBeVisible()
	})

	test('renders note without edit/delete for anonymous user', async ({ page }) => {
		await page.goto('/users/kody/notes/d27a197e')
		// Anonymous users should not see edit/delete buttons in the floating toolbar
		// The "Edit" button (exact match, as a button/link) should not be visible
		await expect(page.getByRole('link', { name: 'Edit', exact: true })).not.toBeVisible()
		await expect(page.getByRole('button', { name: /delete/i })).not.toBeVisible()
	})

	test('shows edit and delete buttons for owner', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/d27a197e')
		// Edit is a link/button in the floating toolbar - use exact match to avoid sidebar note titles
		await expect(page.getByRole('link', { name: 'Edit', exact: true })).toBeVisible()
		await expect(page.getByRole('button', { name: /delete/i })).toBeVisible()
	})

	test('note has images', async ({ page }) => {
		await page.goto('/users/kody/notes/d27a197e')
		// This note has images (cuteKoala, koalaEating)
		await expect(page.locator('ul img').first()).toBeVisible()
	})

	test('note without images renders just text', async ({ page }) => {
		// Note 260366b1 "Not bears" has no images
		await page.goto('/users/kody/notes/260366b1')
		await expect(page.getByRole('heading', { name: /not bears/i })).toBeVisible()
		await expect(page.getByText(/marsupials/i)).toBeVisible()
	})
})

test.describe('Note Create', () => {
	test('new note page requires authentication', async ({ page }) => {
		await page.goto('/users/kody/notes/new')
		// Should redirect to login
		await expect(page).toHaveURL(/\/login/)
	})

	test('new note form renders for authenticated user', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/new')
		await expect(page.getByLabel('Title')).toBeVisible()
		await expect(page.getByLabel('Content')).toBeVisible()
		await expect(page.getByRole('button', { name: /submit/i })).toBeVisible()
		await expect(page.getByRole('button', { name: /reset/i })).toBeVisible()
	})

	test('validates title is required', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/new')
		// Fill content but not title
		await page.getByLabel('Content').fill('Some content without title')
		await page.getByRole('button', { name: /submit/i }).click()
		// Should show validation error
		await expect(page.getByText(/too short|required|minimum/i)).toBeVisible()
	})

	test('validates content is required', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/new')
		await page.getByLabel('Title').fill('Title without content')
		await page.getByRole('button', { name: /submit/i }).click()
		await expect(page.getByText(/too short|required|minimum/i)).toBeVisible()
	})

	test('creates a new note successfully', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/new')

		const uniqueTitle = `Test Note ${Date.now()}`
		const uniqueContent = `Test content created at ${Date.now()}`

		await page.getByLabel('Title').fill(uniqueTitle)
		await page.getByLabel('Content').fill(uniqueContent)
		await page.getByRole('button', { name: /submit/i }).click()

		// Should navigate to the new note
		await expect(page).toHaveURL(/\/users\/kody\/notes\/[a-zA-Z0-9]+$/)
		await expect(page.getByRole('heading', { name: uniqueTitle })).toBeVisible()
	})

	test('reset button clears the form', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/new')

		await page.getByLabel('Title').fill('Test title to reset')
		await page.getByLabel('Content').fill('Test content to reset')
		await page.getByRole('button', { name: /reset/i }).click()

		await expect(page.getByLabel('Title')).toHaveValue('')
		await expect(page.getByLabel('Content')).toHaveValue('')
	})

	test('can add image slot', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/new')
		// Should have an "add image" button
		await expect(page.getByRole('button', { name: /add image/i })).toBeVisible()
		// Click to add another image slot
		await page.getByRole('button', { name: /add image/i }).click()
		// Should now have 2 image slots (one default + one added)
		const imageSections = page.locator('fieldset')
		await expect(imageSections).toHaveCount(2)
	})
})

test.describe('Note Edit', () => {
	test('edit note page requires authentication', async ({ page }) => {
		await page.goto('/users/kody/notes/d27a197e/edit')
		await expect(page).toHaveURL(/\/login/)
	})

	test('edit form is pre-filled with existing note content', async ({ page }) => {
		await loginAsKody(page)
		await page.goto('/users/kody/notes/d27a197e/edit')
		await expect(page.getByLabel('Title')).toHaveValue('Basic Koala Facts')
		await expect(page.getByLabel('Content')).toContainText('eucalyptus forests')
	})

	test('can navigate to edit and submit form', async ({ page }) => {
		await loginAsKody(page)

		// Navigate directly to an existing note's edit page
		await page.goto('/users/kody/notes/9f4308be/edit')
		await page.waitForLoadState('domcontentloaded')

		// The edit form should be visible with current note values
		await expect(page.getByLabel('Title')).toBeVisible()
		await expect(page.getByLabel('Title')).toHaveValue('Onewheel Tricks')

		// Change the title, save, then restore
		const tempTitle = `Temp ${Date.now()}`
		await page.getByLabel('Title').clear()
		await page.getByLabel('Title').fill(tempTitle)
		await page.getByRole('button', { name: /submit/i }).click()

		// Should navigate back to note view with updated title
		await expect(page).toHaveURL(/\/users\/kody\/notes\/9f4308be$/)
		await expect(page.getByRole('heading', { name: tempTitle })).toBeVisible()

		// Restore the original title
		await page.goto('/users/kody/notes/9f4308be/edit')
		await page.waitForLoadState('domcontentloaded')
		await page.getByLabel('Title').clear()
		await page.getByLabel('Title').fill('Onewheel Tricks')
		await page.getByRole('button', { name: /submit/i }).click()
		await expect(page).toHaveURL(/\/users\/kody\/notes\/9f4308be$/)
	})
})

test.describe('Note Delete', () => {
	test('can delete a note', async ({ page }) => {
		await loginAsKody(page)

		// Create a note to delete
		await page.goto('/users/kody/notes/new')
		const uniqueTitle = `Delete Test ${Date.now()}`
		await page.getByLabel('Title').fill(uniqueTitle)
		await page.getByLabel('Content').fill('Content to be deleted')
		await page.getByRole('button', { name: /submit/i }).click()
		await expect(page).toHaveURL(/\/users\/kody\/notes\/[a-zA-Z0-9]+$/)

		// Delete the note
		await page.getByRole('button', { name: /delete/i }).click()

		// Should redirect to notes list with toast
		await expect(page).toHaveURL(/\/users\/kody\/notes$/)
		// The deleted note should no longer appear in the sidebar
		await expect(page.getByRole('link', { name: uniqueTitle })).not.toBeVisible()
	})
})

test.describe('Note Navigation', () => {
	test('navigating between notes works', async ({ page }) => {
		await page.goto('/users/kody/notes')

		// Click on a note
		await page.getByRole('link', { name: /basic koala facts/i }).click()
		await expect(page.getByRole('heading', { name: /basic koala facts/i })).toBeVisible()

		// Click another note
		await page.getByRole('link', { name: /koalas like to cuddle/i }).click()
		await expect(page.getByRole('heading', { name: /koalas like to cuddle/i })).toBeVisible()
	})

	test('back link to user profile from notes sidebar', async ({ page }) => {
		await page.goto('/users/kody/notes')
		// The user image/name in sidebar is a link to user profile
		await page.getByRole('link', { name: /kody's notes/i }).click()
		await expect(page).toHaveURL(/\/users\/kody$/)
	})
})
