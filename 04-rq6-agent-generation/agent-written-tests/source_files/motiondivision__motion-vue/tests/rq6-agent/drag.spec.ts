import { expect, test } from '@playwright/test'

test.describe('Drag - Basic', () => {
  test('page loads with heading and drag container', async ({ page }) => {
    await page.goto('/drag')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Drag Animations' })).toBeVisible()
    await expect(page.getByText('Drag the box within the container')).toBeVisible()
  })

  test('drag container is present in the page', async ({ page }) => {
    await page.goto('/drag')
    await page.waitForLoadState('networkidle')

    // The draggable Motion component should be present
    // It has cursor-move class
    const dragBox = page.locator('.cursor-move')
    await expect(dragBox).toBeVisible()
  })

  test('draggable element can be dragged within container', async ({ page }) => {
    await page.goto('/drag')
    await page.waitForLoadState('networkidle')

    const dragBox = page.locator('.cursor-move')
    await expect(dragBox).toBeVisible()

    const boxBounds = await dragBox.boundingBox()
    expect(boxBounds).not.toBeNull()

    if (boxBounds) {
      const startX = boxBounds.x + boxBounds.width / 2
      const startY = boxBounds.y + boxBounds.height / 2

      // Drag a small amount
      await page.mouse.move(startX, startY)
      await page.mouse.down()
      await page.mouse.move(startX + 30, startY + 30, { steps: 5 })
      await page.waitForTimeout(100)
      await page.mouse.up()
      await page.waitForTimeout(200)
    }

    // Element should still be visible after drag
    await expect(dragBox).toBeVisible()
  })
})

test.describe('Drag - Constraints Animation', () => {
  test('page loads with drag boxes', async ({ page }) => {
    await page.goto('/drag/constraints-animation')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('drag-box-1')).toBeVisible()
    await expect(page.getByTestId('drag-box-2')).toBeVisible()
  })

  test('drag-box-1 contains Drag Me text', async ({ page }) => {
    await page.goto('/drag/constraints-animation')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('drag-box-1')).toContainText('Drag Me')
  })

  test('drag-box-2 contains Snap text', async ({ page }) => {
    await page.goto('/drag/constraints-animation')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('drag-box-2')).toContainText('Snap')
  })

  test('section heading is present', async ({ page }) => {
    await page.goto('/drag/constraints-animation')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Test 2: dragSnapToOrigin' })).toBeVisible()
  })
})

test.describe('Drag - Scroll While Drag', () => {
  test('page loads with drag heading', async ({ page }) => {
    await page.goto('/drag/drag-scroll-while-drag')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Scroll While Drag Test' })).toBeVisible()
  })

  test('draggable-in-scrollable element is present', async ({ page }) => {
    await page.goto('/drag/drag-scroll-while-drag')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('draggable-in-scrollable')).toBeVisible()
    await expect(page.getByTestId('draggable-in-scrollable')).toContainText('Drag')
  })

  test('window scroll drag element is present', async ({ page }) => {
    await page.goto('/drag/drag-scroll-while-drag')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('draggable-window-scroll')).toBeVisible()
    await expect(page.getByTestId('draggable-window-scroll')).toContainText('Drag')
  })

  test('element and window scroll sections shown', async ({ page }) => {
    await page.goto('/drag/drag-scroll-while-drag')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'Element Scroll' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Window Scroll' })).toBeVisible()
  })
})

test.describe('Drag - Snap to Origin', () => {
  test('page loads with snap-to-origin heading', async ({ page }) => {
    await page.goto('/drag/drag-snap-to-origin')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'dragSnapToOrigin Test' })).toBeVisible()
  })

  test('snap-to-origin box is present', async ({ page }) => {
    await page.goto('/drag/drag-snap-to-origin')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('snap-to-origin-box')).toBeVisible()
    await expect(page.getByTestId('snap-to-origin-box')).toContainText('Snap')
  })

  test('drag count and snap back count start at 0', async ({ page }) => {
    await page.goto('/drag/drag-snap-to-origin')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Drag count: 0')).toBeVisible()
    await expect(page.getByText('Snap back count: 0')).toBeVisible()
  })

  test('dragging increments counters', async ({ page }) => {
    await page.goto('/drag/drag-snap-to-origin')
    await page.waitForLoadState('networkidle')

    const box = page.getByTestId('snap-to-origin-box')
    const bounds = await box.boundingBox()
    expect(bounds).not.toBeNull()

    if (bounds) {
      const cx = bounds.x + bounds.width / 2
      const cy = bounds.y + bounds.height / 2

      await page.mouse.move(cx, cy)
      await page.mouse.down()
      await page.mouse.move(cx + 50, cy + 30, { steps: 5 })
      await page.waitForTimeout(100)
      await page.mouse.up()
      await page.waitForTimeout(200)
    }

    await expect(page.getByText('Drag count: 1')).toBeVisible()
    await expect(page.getByText('Snap back count: 1')).toBeVisible()
  })
})
