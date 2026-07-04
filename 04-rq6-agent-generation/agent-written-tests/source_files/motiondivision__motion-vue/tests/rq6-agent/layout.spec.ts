import { expect, test } from '@playwright/test'

test.describe('Layout - Layout Mount', () => {
  test('page loads with toggle button', async ({ page }) => {
    await page.goto('/layout/layout-mount')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('#toggle')).toBeVisible()
    await expect(page.locator('#toggle')).toHaveText('Toggle')
  })

  test('container and layout child start hidden', async ({ page }) => {
    await page.goto('/layout/layout-mount')
    await page.waitForLoadState('networkidle')

    // Initially show = false, container should not be in DOM
    await expect(page.locator('#container')).not.toBeVisible()
    await expect(page.locator('#layout-child')).not.toBeVisible()
  })

  test('toggle shows container with layout child', async ({ page }) => {
    await page.goto('/layout/layout-mount')
    await page.waitForLoadState('networkidle')

    await page.locator('#toggle').click()
    await page.waitForTimeout(400)

    await expect(page.locator('#container')).toBeVisible()
    await expect(page.locator('#layout-child')).toBeVisible()
  })

  test('toggle hides container after showing', async ({ page }) => {
    await page.goto('/layout/layout-mount')
    await page.waitForLoadState('networkidle')

    // Show
    await page.locator('#toggle').click()
    await page.waitForTimeout(400)
    await expect(page.locator('#container')).toBeVisible()

    // Hide
    await page.locator('#toggle').click()
    await page.waitForTimeout(400)
    await expect(page.locator('#container')).not.toBeVisible()
  })

  test('layout child has correct dimensions when visible', async ({ page }) => {
    await page.goto('/layout/layout-mount')
    await page.waitForLoadState('networkidle')

    await page.locator('#toggle').click()
    await page.waitForTimeout(400)

    const child = page.locator('#layout-child')
    await expect(child).toBeVisible()

    const box = await child.boundingBox()
    expect(box).not.toBeNull()
    if (box) {
      // The child should be 100x100 pixels (from style="width: 100px; height: 100px;")
      expect(box.width).toBeCloseTo(100, 0)
      expect(box.height).toBeCloseTo(100, 0)
    }
  })
})
