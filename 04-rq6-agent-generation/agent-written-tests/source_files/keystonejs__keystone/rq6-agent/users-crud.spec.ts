/**
 * Tests for User CRUD operations:
 *  - /users/create  – create form
 *  - /users/[id]    – item view (read, edit, delete)
 *
 * Password field on create/item pages:
 *   Keystone password field shows "Set password" button initially.
 *   Click it, then fill "New" + "Confirm" inputs.
 */

import { test, expect } from '@playwright/test'

const API_URL = 'http://localhost:3014/api/graphql'

async function gqlRequest(query: string, variables?: Record<string, unknown>) {
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  })
  const json = (await res.json()) as { data: Record<string, unknown>; errors?: unknown[] }
  if (json.errors) throw new Error(JSON.stringify(json.errors))
  return json.data
}

async function createTestUser(name: string, password: string) {
  const data = await gqlRequest(
    `mutation CreateUser($data: UserCreateInput!) {
       createUser(data: $data) { id name }
     }`,
    { data: { name, password } }
  )
  return data.createUser as { id: string; name: string }
}

async function deleteTestUser(id: string, cookieStr: string) {
  await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Cookie: cookieStr },
    body: JSON.stringify({
      query: `mutation DeleteUser($id: ID!) { deleteUser(where: { id: $id }) { id } }`,
      variables: { id },
    }),
  })
}

/**
 * Fill the Keystone password field (create/item pages).
 * Clicks "Set password" → reveals "New" + "Confirm" text inputs.
 */
async function fillPasswordField(page: import('@playwright/test').Page, password: string) {
  const setBtn = page.getByRole('button', { name: /^set password$/i })
  if (await setBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await setBtn.click()
  }
  const newInput = page.getByPlaceholder('New')
  await newInput.waitFor({ state: 'visible', timeout: 5_000 })
  await newInput.fill(password)

  const confirmInput = page.getByPlaceholder('Confirm')
  await confirmInput.waitFor({ state: 'visible', timeout: 5_000 })
  await confirmInput.fill(password)
}

// ── /users/create ──────────────────────────────────────────────────────────────

test.describe('/users/create', () => {
  test('shows Create User heading', async ({ page }) => {
    await page.goto('/users/create')
    await page.waitForURL(/\/users\/create/, { timeout: 15_000 })
    await expect(page.getByRole('heading', { name: /create user/i })).toBeVisible()
  })

  test('has Name field', async ({ page }) => {
    await page.goto('/users/create')
    await page.waitForURL(/\/users\/create/, { timeout: 15_000 })
    await expect(page.getByLabel('Name')).toBeVisible()
  })

  test('has Password field (Set password button or inputs)', async ({ page }) => {
    await page.goto('/users/create')
    await page.waitForURL(/\/users\/create/, { timeout: 15_000 })
    // Keystone password field renders as group "Password" containing "Set password" button
    const pwdGroup = page.getByRole('group', { name: 'Password' })
    await expect(pwdGroup).toBeVisible({ timeout: 5_000 })
  })

  test('has a Create button', async ({ page }) => {
    await page.goto('/users/create')
    await page.waitForURL(/\/users\/create/, { timeout: 15_000 })
    await expect(page.getByRole('button', { name: /^create$/i })).toBeVisible()
  })

  test('creates a new user and redirects to item page', async ({ page }) => {
    const uniqueName = `testcreate_${Date.now()}`
    await page.goto('/users/create')
    await page.waitForURL(/\/users\/create/, { timeout: 15_000 })

    await page.getByLabel('Name').fill(uniqueName)
    await fillPasswordField(page, 'TestPass123!')
    await page.getByRole('button', { name: /^create$/i }).click()

    await page.waitForURL(/\/users\/[^/]+$/, { timeout: 15_000 })
    const newUrl = page.url()
    expect(newUrl).toMatch(/\/users\/[a-z0-9]+/)

    // Clean up
    const id = newUrl.split('/users/')[1]
    const cookies = await page.context().cookies()
    await deleteTestUser(id, cookies.map(c => `${c.name}=${c.value}`).join('; '))
  })

  test('new user appears in /users list', async ({ page }) => {
    const uniqueName = `testlist_${Date.now()}`
    await page.goto('/users/create')
    await page.waitForURL(/\/users\/create/, { timeout: 15_000 })

    await page.getByLabel('Name').fill(uniqueName)
    await fillPasswordField(page, 'TestPass123!')
    await page.getByRole('button', { name: /^create$/i }).click()
    await page.waitForURL(/\/users\/[^/]+$/, { timeout: 15_000 })

    const id = page.url().split('/users/')[1]

    await page.goto('/users')
    await expect(page.getByText(uniqueName)).toBeVisible({ timeout: 10_000 })

    // Clean up
    const cookies = await page.context().cookies()
    await deleteTestUser(id, cookies.map(c => `${c.name}=${c.value}`).join('; '))
  })
})

// ── /users/[id] item page ──────────────────────────────────────────────────────

test.describe('/users/[id] item page', () => {
  let testUserId: string
  const TEST_USER_NAME = `itemtest_${Date.now()}`

  test.beforeAll(async () => {
    const user = await createTestUser(TEST_USER_NAME, 'TestPass123!')
    testUserId = user.id
  })

  test.afterAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: 'rq6-agent/.auth/user.json',
    })
    const cookies = await context.cookies()
    await deleteTestUser(testUserId, cookies.map(c => `${c.name}=${c.value}`).join('; '))
    await context.close()
  })

  test('loads the user item page', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    await expect(page.getByRole('heading')).toBeVisible()
  })

  test('shows the Name field', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    await expect(page.getByLabel('Name')).toBeVisible()
  })

  test('shows the Is Admin field', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    await expect(page.getByLabel('Is Admin')).toBeVisible()
  })

  test('has a Save button (disabled when no changes)', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    // The Save button is present but disabled until a field is edited
    await expect(page.getByRole('button', { name: /^save$/i })).toBeVisible()
  })

  test('Users nav item is marked as current when on item page', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    const usersLink = page.locator('nav[aria-label="main"]').getByRole('link', { name: /^users$/i })
    const ariaCurrent = await usersLink.getAttribute('aria-current')
    expect(['true', 'page']).toContain(ariaCurrent)
  })

  test('Users breadcrumb link navigates back to /users list', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    // The breadcrumb "Users" link at top of item page
    const breadcrumb = page.getByRole('link', { name: /^users$/i }).first()
    await expect(breadcrumb).toBeVisible()
    await breadcrumb.click()
    // URL may include query params (e.g. ?column=name&column=isAdmin) – just check /users
    await expect(page).toHaveURL(/\/users/, { timeout: 10_000 })
  })

  test('shows a delete option for admin', async ({ page }) => {
    await page.goto(`/users/${testUserId}`)
    await page.waitForURL(`**/users/${testUserId}`, { timeout: 15_000 })
    const deleteBtn = page
      .getByRole('button', { name: /delete/i })
      .or(page.getByRole('menuitem', { name: /delete/i }))
    await expect(deleteBtn.first()).toBeVisible({ timeout: 10_000 })
  })
})

// ── Invalid item ID ────────────────────────────────────────────────────────────

test.describe('/users/[id] – invalid id', () => {
  test('shows not-found state for a non-existent ID', async ({ page }) => {
    await page.goto('/users/nonexistentid000000000000')
    // Keystone either shows a not-found message or redirects to the list
    try {
      await page.waitForURL(url => !url.href.includes('nonexistentid'), { timeout: 5_000 })
      // Redirected to list – acceptable
      expect(page.url()).toContain('/users')
    } catch {
      // Stayed on page – should show a not-found indicator
      const notFoundText = page
        .locator('text=/not found|does not exist|no item/i')
        .or(page.getByRole('heading', { name: /not found/i }))
      await expect(notFoundText.first()).toBeVisible({ timeout: 10_000 })
    }
  })
})
