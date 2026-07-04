import { expect, test } from '@playwright/test'

test.describe('AnimatePresence - Basic', () => {
  test('page loads with toggle button', async ({ page }) => {
    await page.goto('/animate-presence')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'AnimatePresence Demo' })).toBeVisible()
    await expect(page.locator('#toggle')).toBeVisible()
  })

  test('toggle shows and hides the animated item', async ({ page }) => {
    await page.goto('/animate-presence')
    await page.waitForLoadState('networkidle')

    // Initially hidden (show = false)
    await expect(page.locator('#animate-presence-item')).not.toBeVisible()

    // Click Show
    await page.locator('#toggle').click()
    await page.waitForTimeout(400)
    await expect(page.locator('#animate-presence-item')).toBeVisible()

    // Click Hide
    await page.locator('#toggle').click()
    await page.waitForTimeout(400)
    await expect(page.locator('#animate-presence-item')).not.toBeVisible()
  })

  test('toggle button label updates', async ({ page }) => {
    await page.goto('/animate-presence')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('#toggle')).toHaveText('Show')
    await page.locator('#toggle').click()
    await expect(page.locator('#toggle')).toHaveText('Hide')
  })
})

test.describe('AnimatePresence - Group AnimatePresence', () => {
  test('page loads with toggle button', async ({ page }) => {
    await page.goto('/animate-presence/group-animatepresence')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('button', { name: 'Toggle open' })).toBeVisible()
  })

  test('toggle expands and collapses content', async ({ page }) => {
    await page.goto('/animate-presence/group-animatepresence')
    await page.waitForLoadState('networkidle')

    // Initially closed - pre text not visible
    const pre = page.locator('pre')
    await expect(pre).not.toBeVisible()

    await page.getByRole('button', { name: 'Toggle open' }).click()
    await page.waitForTimeout(400)
    await expect(pre).toBeVisible()

    await page.getByRole('button', { name: 'Toggle open' }).click()
    await page.waitForTimeout(400)
    await expect(pre).not.toBeVisible()
  })
})

test.describe('AnimatePresence - Multi Motion', () => {
  test('page loads with all motion components visible', async ({ page }) => {
    await page.goto('/animate-presence/multi-motion')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Multiple Motion Components Test' })).toBeVisible()
    await expect(page.locator('#toggle')).toBeVisible()

    // Initially visible (show = true)
    await expect(page.locator('#motion-1')).toBeVisible()
    await expect(page.locator('#motion-2')).toBeVisible()
    await expect(page.locator('#motion-3')).toBeVisible()
  })

  test('exit status starts as present', async ({ page }) => {
    await page.goto('/animate-presence/multi-motion')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('#exit-status')).toHaveText('present')
  })

  test('hide removes motion components and fires exit complete', async ({ page }) => {
    await page.goto('/animate-presence/multi-motion')
    await page.waitForLoadState('networkidle')

    // Hide
    await page.locator('#toggle').click()
    await page.waitForTimeout(800)

    await expect(page.locator('#motion-1')).not.toBeVisible()
    await expect(page.locator('#motion-2')).not.toBeVisible()
    await expect(page.locator('#motion-3')).not.toBeVisible()
    await expect(page.locator('#exit-status')).toHaveText('exited')
  })

  test('show restores motion components', async ({ page }) => {
    await page.goto('/animate-presence/multi-motion')
    await page.waitForLoadState('networkidle')

    // Hide
    await page.locator('#toggle').click()
    await page.waitForTimeout(800)

    // Show again
    await page.locator('#toggle').click()
    await page.waitForTimeout(600)

    await expect(page.locator('#motion-1')).toBeVisible()
    await expect(page.locator('#motion-2')).toBeVisible()
    await expect(page.locator('#motion-3')).toBeVisible()
  })
})

test.describe('AnimatePresence - Nested Motion', () => {
  test('page loads with all nested elements visible', async ({ page }) => {
    await page.goto('/animate-presence/nested-motion')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Nested Motion Components Test' })).toBeVisible()
    await expect(page.locator('#toggle')).toBeVisible()

    // Initially show = true
    await expect(page.locator('#parent-motion')).toBeVisible()
    await expect(page.locator('#child-motion-1')).toBeVisible()
    await expect(page.locator('#child-motion-2')).toBeVisible()
    await expect(page.locator('#grandchild-motion')).toBeVisible()
  })

  test('toggle hides all nested motion elements', async ({ page }) => {
    await page.goto('/animate-presence/nested-motion')
    await page.waitForLoadState('networkidle')

    await page.locator('#toggle').click()
    await page.waitForTimeout(700)

    await expect(page.locator('#parent-motion')).not.toBeVisible()
  })

  test('toggle restores all nested elements', async ({ page }) => {
    await page.goto('/animate-presence/nested-motion')
    await page.waitForLoadState('networkidle')

    // Hide
    await page.locator('#toggle').click()
    await page.waitForTimeout(700)

    // Show
    await page.locator('#toggle').click()
    await page.waitForTimeout(700)

    await expect(page.locator('#parent-motion')).toBeVisible()
    await expect(page.locator('#child-motion-1')).toBeVisible()
    await expect(page.locator('#child-motion-2')).toBeVisible()
    await expect(page.locator('#grandchild-motion')).toBeVisible()
  })
})

test.describe('AnimatePresence - v-show Shared Layout', () => {
  test('page loads with small and large boxes', async ({ page }) => {
    await page.goto('/animate-presence/v-show-shared-layout')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /v-show Shared Layout/ })).toBeVisible()
    await expect(page.locator('#toggle')).toBeVisible()

    // Both boxes exist in DOM (v-show keeps them, just hides)
    await expect(page.locator('#small-box')).toBeVisible()
    await expect(page.locator('#large-box')).not.toBeVisible()
  })

  test('animation state indicators exist', async ({ page }) => {
    await page.goto('/animate-presence/v-show-shared-layout')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('#animation-started')).toBeVisible()
    await expect(page.locator('#animation-completed')).toBeVisible()
  })

  test('toggle switches between small and large boxes', async ({ page }) => {
    await page.goto('/animate-presence/v-show-shared-layout')
    await page.waitForLoadState('networkidle')

    await page.locator('#toggle').click()
    await page.waitForTimeout(600)

    await expect(page.locator('#small-box')).not.toBeVisible()
    await expect(page.locator('#large-box')).toBeVisible()
  })
})

test.describe('AnimatePresence - Variants', () => {
  test('page loads with toggle button and list', async ({ page }) => {
    await page.goto('/animate-presence/variants')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.getByRole('button').filter({ hasText: /Hide|Show/ })
    await expect(toggleBtn).toBeVisible()
  })

  test('initially visible list can be hidden and shown', async ({ page }) => {
    await page.goto('/animate-presence/variants')
    await page.waitForLoadState('networkidle')

    const list = page.locator('ul')
    await expect(list).toBeVisible()

    // Hide
    await page.getByRole('button').filter({ hasText: /Hide/ }).click()
    await page.waitForTimeout(1500)
    await expect(list).not.toBeVisible()

    // Show
    await page.getByRole('button').filter({ hasText: /Show/ }).click()
    await page.waitForTimeout(1500)
    await expect(list).toBeVisible()
  })

  test('list contains expected items', async ({ page }) => {
    await page.goto('/animate-presence/variants')
    await page.waitForLoadState('networkidle')

    const listItems = page.locator('li')
    await expect(listItems).toHaveCount(3)
  })
})
