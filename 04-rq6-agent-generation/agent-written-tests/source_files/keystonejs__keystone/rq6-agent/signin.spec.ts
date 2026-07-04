/**
 * Tests for the /signin page – unauthenticated flow.
 *
 * @keystar/ui PasswordField renders a textbox accessible by the label "Password"
 * and with name="password".  We use the name attribute for unambiguous targeting.
 */

import { test, expect } from '@playwright/test'

const ADMIN_NAME = 'admin'
const ADMIN_PASSWORD = 'Admin1234!'

/** Return the password <input> on the sign-in page. */
function passwordInput(page: import('@playwright/test').Page) {
  return page.locator('input[name="password"]')
}

test.describe('/signin page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/signin')
    await page.waitForURL('**/signin', { timeout: 15_000 })
  })

  test('renders the sign-in heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible()
  })

  test('shows a logo / brand mark', async ({ page }) => {
    // The Keystone logo is a link with accessible name "Keystone" (contains SVG + text)
    const logo = page.getByRole('link', { name: /keystone/i })
    await expect(logo).toBeVisible()
  })

  test('has Name field', async ({ page }) => {
    await expect(page.getByLabel('Name')).toBeVisible()
  })

  test('has Password field', async ({ page }) => {
    await expect(passwordInput(page)).toBeVisible()
  })

  test('has a Sign in button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /^sign in$/i })).toBeVisible()
  })

  test('shows failure notice for wrong credentials', async ({ page }) => {
    await page.getByLabel('Name').fill('notauser')
    await passwordInput(page).fill('wrongpassword')

    // Capture the sign-in mutation response.
    // The KsAuthSignin mutation aliases the result as 'authenticate'.
    const [response] = await Promise.all([
      page.waitForResponse(
        async r => {
          if (!r.url().includes('/api/graphql') || r.request().method() !== 'POST') return false
          try {
            const json = await r.json()
            // Match the sign-in mutation's aliased 'authenticate' field
            return json?.data?.authenticate != null
          } catch {
            return false
          }
        },
        { timeout: 10_000 }
      ),
      page.getByRole('button', { name: /^sign in$/i }).click(),
    ])

    // Server returns "Authentication failed." for wrong credentials
    const json = (await response.json()) as {
      data: { authenticate: { message?: string } }
    }
    expect(json.data.authenticate.message).toBe('Authentication failed.')

    // Must NOT navigate away from /signin on authentication failure
    expect(page.url()).toContain('/signin')
  })

  test('does not navigate away with empty Name', async ({ page }) => {
    // Click Sign in without filling anything – HTML validation prevents submission
    await page.getByRole('button', { name: /^sign in$/i }).click()
    await page.waitForTimeout(500)
    expect(page.url()).toContain('/signin')
  })

  test('successful sign-in redirects away from /signin', async ({ page }) => {
    await page.getByLabel('Name').fill(ADMIN_NAME)
    await passwordInput(page).fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: /^sign in$/i }).click()

    await page.waitForURL(url => !url.href.includes('/signin'), { timeout: 15_000 })
    const url = page.url()
    expect(url).not.toContain('/signin')
    expect(url).not.toContain('/init')
  })
})
