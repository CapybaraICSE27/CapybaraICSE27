import { expect, test } from '@playwright/test'

test.describe('Dynamic Variant', () => {
  test('page loads with toggle and motion buttons', async ({ page }) => {
    await page.goto('/dynamic-variant')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('toggle-btn')).toBeVisible()
    await expect(page.getByTestId('motion-btn')).toBeVisible()
    await expect(page.getByTestId('motion-btn')).toHaveText('CLICK ME')
  })

  test('toggle button is interactive', async ({ page }) => {
    await page.goto('/dynamic-variant')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('toggle-btn')).toHaveText('Toggle')

    await page.getByTestId('toggle-btn').click()
    await page.waitForTimeout(200)

    // Button is still present after click
    await expect(page.getByTestId('toggle-btn')).toBeVisible()
    await expect(page.getByTestId('motion-btn')).toBeVisible()
  })
})

test.describe('Pop Layout', () => {
  test('page loads with add button and initial item', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('button', { name: 'Add item' })).toBeVisible()
  })

  test('initial item 0 is present', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    // The initial item is 0
    await expect(page.getByText('0')).toBeVisible()
  })

  test('popLayout checkbox is present', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    const checkbox = page.locator('input[type="checkbox"]')
    await expect(checkbox).toBeVisible()
  })

  test('add item button updates state (data-key reflects items.length)', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    // data-key is set to items.length on the rendered li
    const li = page.locator('[data-pop-id="122"] li')
    await expect(li).toHaveAttribute('data-key', '1')

    // Click "Add item" - count increments and items array grows
    await page.getByRole('button', { name: 'Add item' }).click()
    await page.waitForTimeout(300)

    // data-key should now be 2 (items.length = 2)
    await expect(li).toHaveAttribute('data-key', '2')
  })

  test('switching to popLayout mode and adding items shows new items', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    // Switch to popLayout mode so items appear immediately
    const checkbox = page.locator('input[type="checkbox"]')
    await checkbox.click()
    await page.waitForTimeout(200)

    // Add item 1
    await page.getByRole('button', { name: 'Add item' }).click()
    await page.waitForTimeout(500)

    // With popLayout mode, new items should appear immediately
    // There should now be 2 items (0 and 1)
    const items = page.locator('[data-pop-id="122"] li')
    await expect(items).toHaveCount(2)
  })

  test('clicking an item removes it (popLayout mode)', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    // Switch to popLayout mode
    await page.locator('input[type="checkbox"]').click()
    await page.waitForTimeout(200)

    // Add item 1
    await page.getByRole('button', { name: 'Add item' }).click()
    await page.waitForTimeout(500)

    const items = page.locator('[data-pop-id="122"] li')
    await expect(items).toHaveCount(2)

    // Click the second item (item 1) to remove it
    await items.nth(1).click()
    await page.waitForTimeout(1000)

    await expect(items).toHaveCount(1)
  })

  test('popLayout checkbox can be toggled', async ({ page }) => {
    await page.goto('/pop-layout')
    await page.waitForLoadState('networkidle')

    const checkbox = page.locator('input[type="checkbox"]')
    const initialState = await checkbox.isChecked()

    await checkbox.click()
    await page.waitForTimeout(100)

    const newState = await checkbox.isChecked()
    expect(newState).toBe(!initialState)
  })
})

test.describe('Reorder - Auto Scroll', () => {
  test('page loads with reorder heading', async ({ page }) => {
    await page.goto('/reorder/auto-scroll')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Reorder Auto-Scroll Test' })).toBeVisible()
  })

  test('vertical scroll container with items is present', async ({ page }) => {
    await page.goto('/reorder/auto-scroll')
    await page.waitForLoadState('networkidle')

    const scrollContainer = page.getByTestId('scroll-container')
    await expect(scrollContainer).toBeVisible()
  })

  test('horizontal scroll container with items is present', async ({ page }) => {
    await page.goto('/reorder/auto-scroll')
    await page.waitForLoadState('networkidle')

    const hScrollContainer = page.getByTestId('horizontal-scroll-container')
    await expect(hScrollContainer).toBeVisible()
  })

  test('vertical reorder has initial items visible', async ({ page }) => {
    await page.goto('/reorder/auto-scroll')
    await page.waitForLoadState('networkidle')

    // Items 0-5 should be visible in the vertical list
    await expect(page.getByTestId('0')).toBeVisible()
    await expect(page.getByTestId('1')).toBeVisible()
    await expect(page.getByTestId('2')).toBeVisible()
  })

  test('horizontal reorder has initial items visible', async ({ page }) => {
    await page.goto('/reorder/auto-scroll')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('h-1-A')).toBeVisible()
    await expect(page.getByTestId('h-2-B')).toBeVisible()
    await expect(page.getByTestId('h-3-C')).toBeVisible()
  })

  test('vertical and horizontal section headings are shown', async ({ page }) => {
    await page.goto('/reorder/auto-scroll')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Vertical Reorder with Auto-Scroll' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Horizontal Reorder with Auto-Scroll' })).toBeVisible()
  })
})

test.describe('Test Page', () => {
  test('page loads with mount/unmount section', async ({ page }) => {
    await page.goto('/test')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Mount / Unmount' })).toBeVisible()
  })

  test('toggle button is present', async ({ page }) => {
    await page.goto('/test')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.getByRole('button').filter({ hasText: /Hide|Show/ })
    await expect(toggleBtn).toBeVisible()
  })

  test('toggle me text visible initially', async ({ page }) => {
    await page.goto('/test')
    await page.waitForLoadState('networkidle')

    // isVisible = true initially, so "Toggle m" (text is "Toggle m" in the template)
    await expect(page.getByText('Toggle m')).toBeVisible()
  })

  test('hide button hides the element', async ({ page }) => {
    await page.goto('/test')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.getByRole('button').filter({ hasText: /Hide/ })
    await toggleBtn.click()
    await page.waitForTimeout(600)

    await expect(page.getByText('Toggle m')).not.toBeVisible()
  })

  test('show button restores the element', async ({ page }) => {
    await page.goto('/test')
    await page.waitForLoadState('networkidle')

    const toggleBtn = page.getByRole('button').filter({ hasText: /Hide/ })
    await toggleBtn.click()
    await page.waitForTimeout(600)

    await expect(page.getByText('Toggle m')).not.toBeVisible()

    await page.getByRole('button').filter({ hasText: /Show/ }).click()
    await page.waitForTimeout(600)

    await expect(page.getByText('Toggle m')).toBeVisible()
  })
})

test.describe('Transition Arc', () => {
  test('page loads with all 4 sections', async ({ page }) => {
    await page.goto('/transition-arc')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: /keyframe arc.*ping-pong/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: /keyframe arc.*rotate/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: /keyframe arc.*axis-change/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: /layout arc/i })).toBeVisible()
  })

  test('ping-pong toggle button is present and works', async ({ page }) => {
    await page.goto('/transition-arc')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('ping-btn')).toBeVisible()
    await expect(page.getByTestId('ping-box')).toBeVisible()

    await page.getByTestId('ping-btn').click()
    await page.waitForTimeout(200)

    // Box is still visible after click
    await expect(page.getByTestId('ping-box')).toBeVisible()
  })

  test('rotate button is present and works', async ({ page }) => {
    await page.goto('/transition-arc')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('rotate-btn')).toBeVisible()
    await expect(page.getByTestId('rotate-box')).toBeVisible()

    await page.getByTestId('rotate-btn').click()
    await page.waitForTimeout(200)
    await expect(page.getByTestId('rotate-box')).toBeVisible()
  })

  test('axis button is present and shows step counter', async ({ page }) => {
    await page.goto('/transition-arc')
    await page.waitForLoadState('networkidle')

    const axisBtn = page.getByTestId('axis-btn')
    await expect(axisBtn).toBeVisible()
    await expect(axisBtn).toContainText('0')

    await expect(page.getByTestId('axis-box')).toBeVisible()

    await axisBtn.click()
    await page.waitForTimeout(200)
    await expect(axisBtn).toContainText('1')
  })

  test('layout swap button is present and switches layout box', async ({ page }) => {
    await page.goto('/transition-arc')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('layout-btn')).toBeVisible()
    await expect(page.getByTestId('layout-box')).toBeVisible()

    await page.getByTestId('layout-btn').click()
    await page.waitForTimeout(1200)

    // Box should still be present (just in different position)
    await expect(page.getByTestId('layout-box')).toBeVisible()
  })
})

test.describe('Home.vue (empty page)', () => {
  test('home page loads without error', async ({ page }) => {
    await page.goto('/home')
    await page.waitForLoadState('networkidle')

    // Page should load successfully (no 404, no JS error)
    await expect(page).toHaveURL('/home')
    // The page is empty but should not throw
  })
})
