/**
 * Tests for the navigation sidebar in the authenticated Admin UI.
 */

import { test, expect } from '@playwright/test'

test.describe('Navigation sidebar', () => {
  test('contains Dashboard and Users nav items', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL(url => !url.href.includes('/signin'), { timeout: 15_000 })
    const nav = page.locator('nav[aria-label="main"]')
    await expect(nav.getByRole('link', { name: /dashboard/i })).toBeVisible()
    await expect(nav.getByRole('link', { name: /users/i })).toBeVisible()
  })

  test('Dashboard link has aria-current="page" when on dashboard', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL(url => !url.href.includes('/signin'), { timeout: 15_000 })
    const dashLink = page.locator('nav[aria-label="main"]').getByRole('link', { name: /dashboard/i })
    const ariaCurrent = await dashLink.getAttribute('aria-current')
    expect(['page', 'true']).toContain(ariaCurrent)
  })

  test('Users link has aria-current when on /users', async ({ page }) => {
    await page.goto('/users')
    await page.waitForURL(/\/users/, { timeout: 15_000 })
    const usersLink = page.locator('nav[aria-label="main"]').getByRole('link', { name: /^users$/i })
    const ariaCurrent = await usersLink.getAttribute('aria-current')
    expect(['page', 'true']).toContain(ariaCurrent)
  })

  test('clicking Dashboard link navigates to /', async ({ page }) => {
    await page.goto('/users')
    await page.waitForURL(/\/users/, { timeout: 15_000 })
    await page.locator('nav[aria-label="main"]').getByRole('link', { name: /dashboard/i }).click()
    await expect(page).toHaveURL(/^\/?$|\/\s*$/, { timeout: 10_000 })
    // Allow for exact / or trailing slash variant
    const url = new URL(page.url())
    expect(url.pathname).toBe('/')
  })

  test('clicking Users link navigates to /users', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL(url => !url.href.includes('/signin'), { timeout: 15_000 })
    await page.locator('nav[aria-label="main"]').getByRole('link', { name: /^users$/i }).click()
    await expect(page).toHaveURL(/\/users/)
  })

  test('logo is visible in nav area', async ({ page }) => {
    await page.goto('/')
    await page.waitForURL(url => !url.href.includes('/signin'), { timeout: 15_000 })
    // The Keystone logo or wordmark should be visible somewhere on the page
    const logo = page.locator('svg').first()
    await expect(logo).toBeVisible()
  })
})
