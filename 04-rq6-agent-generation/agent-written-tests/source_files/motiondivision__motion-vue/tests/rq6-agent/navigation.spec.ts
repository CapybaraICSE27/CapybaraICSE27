import { expect, test } from '@playwright/test'

test.describe('Home / Navigation', () => {
  test('home page loads and shows route links', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Motion Vue Examples' })).toBeVisible()

    // Nav links are rendered
    const links = page.getByRole('link')
    const count = await links.count()
    expect(count).toBeGreaterThan(10)
  })

  test('home page links navigate to correct routes', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Click the animate-presence link (exact match to avoid matching sub-routes)
    const apLink = page.getByRole('link', { name: 'animate-presence', exact: true })
    await expect(apLink).toBeVisible()
    await apLink.click()
    await page.waitForLoadState('networkidle')
    await expect(page).toHaveURL(/animate-presence/)
  })

  test('404 page shows for unknown route', async ({ page }) => {
    await page.goto('/this-route-does-not-exist-at-all')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('404')).toBeVisible()
    await expect(page.getByText('Page not found')).toBeVisible()
  })

  test('404 page Go Home link returns to home', async ({ page }) => {
    await page.goto('/nonexistent-page-xyz')
    await page.waitForLoadState('networkidle')

    await page.getByRole('link', { name: 'Go Home' }).click()
    await page.waitForLoadState('networkidle')

    await expect(page).toHaveURL('/')
    await expect(page.getByRole('heading', { name: 'Motion Vue Examples' })).toBeVisible()
  })
})
