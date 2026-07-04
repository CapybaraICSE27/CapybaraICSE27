/**
 * Tests for the authenticated Dashboard (/).
 * Uses the session state saved by auth.setup.ts.
 */

import { test, expect } from '@playwright/test'

test.describe('Dashboard (/)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    // Ensure we are on the dashboard, not redirected to /signin
    await page.waitForURL(url => !url.href.includes('/signin') && !url.href.includes('/init'), {
      timeout: 15_000,
    })
  })

  test('shows Dashboard heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible()
  })

  test('shows Users list card', async ({ page }) => {
    // The Users card is a heading link on the dashboard
    await expect(page.getByRole('heading', { name: /users/i })).toBeVisible()
  })

  test('Users card shows item count', async ({ page }) => {
    // The count text (e.g. "1 item" or "X items") should be visible
    const countText = page.locator('text=/\\d+ items?/')
    await expect(countText.first()).toBeVisible()
  })

  test('Users card has an "add" button that navigates to /users/create', async ({ page }) => {
    // The dashboard shows a button "add" (accessible name) for the Users list card
    const addBtn = page.getByRole('button', { name: /^add$/i })
    await expect(addBtn).toBeVisible()
    await addBtn.click()
    await expect(page).toHaveURL(/\/users\/create/, { timeout: 10_000 })
  })

  test('Users card link navigates to /users', async ({ page }) => {
    await page.getByRole('heading', { name: /users/i }).getByRole('link').click()
    await expect(page).toHaveURL(/\/users/)
  })

  test('navigation sidebar contains Dashboard link', async ({ page }) => {
    await expect(page.locator('nav').getByRole('link', { name: /dashboard/i })).toBeVisible()
  })

  test('navigation sidebar contains Users link', async ({ page }) => {
    await expect(page.locator('nav').getByRole('link', { name: /users/i })).toBeVisible()
  })

  test('Dashboard nav link is marked as current page', async ({ page }) => {
    const dashboardLink = page.locator('nav').getByRole('link', { name: /dashboard/i })
    const ariaCurrent = await dashboardLink.getAttribute('aria-current')
    expect(['page', 'true']).toContain(ariaCurrent)
  })
})
