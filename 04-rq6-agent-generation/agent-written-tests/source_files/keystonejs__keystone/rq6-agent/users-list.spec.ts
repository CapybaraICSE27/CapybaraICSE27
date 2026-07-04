/**
 * Tests for the /users list page (authenticated).
 */

import { test, expect } from '@playwright/test'

const API_URL = 'http://localhost:3014/api/graphql'

async function gqlRequest(query: string, variables?: Record<string, unknown>) {
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  })
  const json = await res.json()
  if (json.errors) throw new Error(JSON.stringify(json.errors))
  return json.data
}

test.describe('/users list page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/users')
    await page.waitForURL(/\/users/, { timeout: 15_000 })
  })

  test('shows Users heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /users/i })).toBeVisible()
  })

  test('shows a table or list of users', async ({ page }) => {
    // Keystone renders items in a table/grid – wait for at least one row
    await expect(
      page.locator('table, [role="grid"], [role="table"]').first()
    ).toBeVisible({ timeout: 10_000 })
  })

  test('shows the admin user in the list', async ({ page }) => {
    // "admin" is the user created in auth.setup
    await expect(page.getByText('admin')).toBeVisible({ timeout: 10_000 })
  })

  test('shows a "New User" create button', async ({ page }) => {
    // Keystone renders a "New User" button (accessible name) in the page banner
    const createBtn = page.getByRole('button', { name: /new user/i })
    await expect(createBtn).toBeVisible()
  })

  test('create button navigates to create form', async ({ page }) => {
    await page.getByRole('button', { name: /new user/i }).click()
    await expect(page).toHaveURL(/\/users\/create/, { timeout: 10_000 })
  })

  test('Users nav item is marked as current', async ({ page }) => {
    const usersLink = page.locator('nav[aria-label="main"]').getByRole('link', { name: /^users$/i })
    const ariaCurrent = await usersLink.getAttribute('aria-current')
    expect(['page', 'true']).toContain(ariaCurrent)
  })

  test('shows item count in the list heading area', async ({ page }) => {
    // The list page shows "X Users" or similar count
    const countText = page.locator('text=/\\d+ (user|users)/i')
    await expect(countText.first()).toBeVisible({ timeout: 10_000 })
  })
})

test.describe('/users list – search', () => {
  test('search field is present', async ({ page }) => {
    await page.goto('/users')
    await page.waitForURL(/\/users/, { timeout: 15_000 })
    // Keystone has a search field on list views
    const searchField = page.getByRole('searchbox').or(page.getByPlaceholder(/search/i))
    await expect(searchField.first()).toBeVisible({ timeout: 10_000 })
  })

  test('searching for existing user shows results', async ({ page }) => {
    await page.goto('/users')
    await page.waitForURL(/\/users/, { timeout: 15_000 })
    const searchField = page.getByRole('searchbox').or(page.getByPlaceholder(/search/i))
    await searchField.first().fill('admin')
    // At least one result should remain visible
    await expect(page.getByText('admin')).toBeVisible({ timeout: 10_000 })
  })

  test('searching for non-existent name shows empty state', async ({ page }) => {
    await page.goto('/users')
    await page.waitForURL(/\/users/, { timeout: 15_000 })
    const searchField = page.getByRole('searchbox').or(page.getByPlaceholder(/search/i))
    await searchField.first().fill('zzznobodyzzzXXX')
    // Keystone shows an empty state or "0 Users"
    await expect(
      page.locator('text=/no (users|items|results)|0 (users|items)/i').first()
    ).toBeVisible({ timeout: 10_000 })
  })
})
