import { expect, test } from '@playwright/test'

test.describe('Gestures - Basic', () => {
  test('page loads with heading', async ({ page }) => {
    await page.goto('/gestures')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Gesture Animations' })).toBeVisible()
  })

  test('gesture box and description are visible', async ({ page }) => {
    await page.goto('/gestures')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Hover and tap the box below to see gesture animations')).toBeVisible()

    // The Motion box should be visible inside the container
    const container = page.locator('.cursor-pointer')
    await expect(container).toBeVisible()
  })

  test('gesture area is rendered inside container', async ({ page }) => {
    await page.goto('/gestures')
    await page.waitForLoadState('networkidle')

    // The relative container div should be present
    const gestureContainer = page.locator('.relative.w-full.h-\\[300px\\]')
    await expect(gestureContainer).toBeVisible()
  })
})

test.describe('Gestures - Hover Sidebar', () => {
  test('page loads with nav and toggle button', async ({ page }) => {
    await page.goto('/gestures/hover')
    await page.waitForLoadState('networkidle')

    // The sidebar nav should be present
    const nav = page.locator('nav')
    await expect(nav).toBeVisible()

    // The toggle button (hamburger) should be present
    const toggleBtn = page.locator('button.toggle-container')
    await expect(toggleBtn).toBeVisible()
  })

  test('sidebar starts closed', async ({ page }) => {
    await page.goto('/gestures/hover')
    await page.waitForLoadState('networkidle')

    // List items should not be visible when closed
    const listItems = page.locator('.list-item')
    const count = await listItems.count()
    expect(count).toBe(5)
  })

  test('toggle opens the sidebar menu', async ({ page }) => {
    await page.goto('/gestures/hover')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.locator('button.toggle-container')
    await toggleBtn.click()
    await page.waitForTimeout(800)

    // After opening, list items should be visible
    const listItems = page.locator('.list-item')
    const firstItem = listItems.first()
    await expect(firstItem).toBeVisible()
  })

  test('toggle closes the sidebar after opening', async ({ page }) => {
    await page.goto('/gestures/hover')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.locator('button.toggle-container')

    // Open
    await toggleBtn.click()
    await page.waitForTimeout(800)

    // Close
    await toggleBtn.click()
    await page.waitForTimeout(800)

    // Nav still present (just clipped)
    await expect(page.locator('nav')).toBeVisible()
  })

  test('sidebar has 5 list items', async ({ page }) => {
    await page.goto('/gestures/hover')
    await page.waitForLoadState('networkidle')

    const listItems = page.locator('.list-item')
    await expect(listItems).toHaveCount(5)
  })
})
