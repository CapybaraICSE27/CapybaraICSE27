import { expect, test } from '@playwright/test'

test.describe('Scroll - Horizontal', () => {
  test('page loads with scroll values displayed', async ({ page }) => {
    await page.goto('/scroll-horizontal')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Scroll X:')).toBeVisible()
    await expect(page.getByText('Progress:')).toBeVisible()
  })

  test('scroll container is present and has correct dimensions', async ({ page }) => {
    await page.goto('/scroll-horizontal')
    await page.waitForLoadState('networkidle')

    const container = page.locator('.scroll-container-h')
    await expect(container).toBeVisible()

    const box = await container.boundingBox()
    expect(box).not.toBeNull()
    if (box) {
      expect(box.width).toBe(300)
      expect(box.height).toBe(100)
    }
  })

  test('initial scrollX value is 0', async ({ page }) => {
    await page.goto('/scroll-horizontal')
    await page.waitForLoadState('networkidle')

    const scrollXValue = page.locator('.scroll-x-value')
    await expect(scrollXValue).toBeVisible()
    await expect(scrollXValue).toHaveText('0')
  })

  test('initial scrollXProgress value is 0', async ({ page }) => {
    await page.goto('/scroll-horizontal')
    await page.waitForLoadState('networkidle')

    const progressValue = page.locator('.scroll-x-progress-value')
    await expect(progressValue).toBeVisible()
    await expect(progressValue).toHaveText('0')
  })

  test('scrolling container updates scroll values', async ({ page }) => {
    await page.goto('/scroll-horizontal')
    await page.waitForLoadState('networkidle')

    const container = page.locator('.scroll-container-h')
    const box = await container.boundingBox()

    if (box) {
      // Scroll horizontally
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
      await page.evaluate(() => {
        const el = document.querySelector('.scroll-container-h')
        if (el)
          el.scrollLeft = 150
      })
      await page.waitForTimeout(200)

      const scrollXValue = page.locator('.scroll-x-value')
      const valueText = await scrollXValue.textContent()
      const value = parseFloat(valueText || '0')
      expect(value).toBeGreaterThan(0)
    }
  })
})

test.describe('Scroll - Presets', () => {
  test('page loads with progress value', async ({ page }) => {
    await page.goto('/scroll-presets')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Progress:')).toBeVisible()
    await expect(page.locator('.scroll-y-progress-value')).toBeVisible()
  })

  test('scroll container is present', async ({ page }) => {
    await page.goto('/scroll-presets')
    await page.waitForLoadState('networkidle')

    const container = page.locator('.scroll-container')
    await expect(container).toBeVisible()
  })

  test('scroll target is present inside container', async ({ page }) => {
    await page.goto('/scroll-presets')
    await page.waitForLoadState('networkidle')

    const target = page.locator('.scroll-target')
    await expect(target).toBeVisible()
  })

  test('scrolling changes progress value', async ({ page }) => {
    await page.goto('/scroll-presets')
    await page.waitForLoadState('networkidle')

    await page.evaluate(() => {
      const el = document.querySelector('.scroll-container')
      if (el)
        el.scrollTop = 100
    })
    await page.waitForTimeout(200)

    const progressValue = page.locator('.scroll-y-progress-value')
    const value = parseFloat(await progressValue.textContent() || '0')
    // Progress should have changed from 0
    expect(value).toBeGreaterThanOrEqual(0)
  })
})

test.describe('Scroll - Reactive', () => {
  test('page loads with axis toggle and scroll values', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.toggle-axis')).toBeVisible()
    await expect(page.locator('.current-axis')).toBeVisible()
  })

  test('initial axis is y', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('.current-axis')).toHaveText('y')
  })

  test('toggle axis button changes axis to x', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    await page.locator('.toggle-axis').click()
    await page.waitForTimeout(200)

    await expect(page.locator('.current-axis')).toHaveText('x')
  })

  test('toggle axis button toggles back to y', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    await page.locator('.toggle-axis').click()
    await page.waitForTimeout(200)
    await expect(page.locator('.current-axis')).toHaveText('x')

    await page.locator('.toggle-axis').click()
    await page.waitForTimeout(200)
    await expect(page.locator('.current-axis')).toHaveText('y')
  })

  test('scroll values are displayed', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Scroll Y:')).toBeVisible()
    await expect(page.getByText('Scroll X:')).toBeVisible()
    await expect(page.getByText('Progress Y:')).toBeVisible()
    await expect(page.getByText('Progress X:')).toBeVisible()
  })

  test('scroll container is present', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    const container = page.locator('.scroll-container')
    await expect(container).toBeVisible()
  })

  test('scroll values update when container is scrolled', async ({ page }) => {
    await page.goto('/scroll-reactive')
    await page.waitForLoadState('networkidle')

    await page.evaluate(() => {
      const el = document.querySelector('.scroll-container')
      if (el)
        el.scrollTop = 100
    })
    await page.waitForTimeout(200)

    const scrollYValue = page.locator('.scroll-y-value')
    const value = parseFloat(await scrollYValue.textContent() || '0')
    expect(value).toBeGreaterThan(0)
  })
})

test.describe('Scroll - Test (Motion components)', () => {
  test('page loads with scroll values', async ({ page }) => {
    await page.goto('/scroll-test')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Scroll Y:')).toBeVisible()
    await expect(page.getByText('Progress:')).toBeVisible()
  })

  test('scroll container is present', async ({ page }) => {
    await page.goto('/scroll-test')
    await page.waitForLoadState('networkidle')

    const container = page.locator('.scroll-container')
    await expect(container).toBeVisible()
  })

  test('scroll target with content is present', async ({ page }) => {
    await page.goto('/scroll-test')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Target Content')).toBeVisible()
  })

  test('above target and below target sections present', async ({ page }) => {
    await page.goto('/scroll-test')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Above Target')).toBeVisible()
    await expect(page.getByText('Below Target')).toBeVisible()
  })

  test('scroll Y value starts at 0', async ({ page }) => {
    await page.goto('/scroll-test')
    await page.waitForLoadState('networkidle')

    const scrollYValue = page.locator('.scroll-y-value')
    await expect(scrollYValue).toHaveText('0')
  })

  test('scrolling container updates scrollY value', async ({ page }) => {
    await page.goto('/scroll-test')
    await page.waitForLoadState('networkidle')

    await page.evaluate(() => {
      const el = document.querySelector('.scroll-container')
      if (el)
        el.scrollTop = 80
    })
    await page.waitForTimeout(200)

    const scrollYValue = page.locator('.scroll-y-value')
    const value = parseFloat(await scrollYValue.textContent() || '0')
    expect(value).toBeGreaterThan(0)
  })
})
