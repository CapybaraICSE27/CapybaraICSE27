import { expect, test } from '@playwright/test'

test.describe('Directive - v-motion', () => {
  test('page loads with v-motion directive heading', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1, name: 'v-motion Directive' })).toBeVisible()
  })

  test('all directive sections are rendered', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    // Check section headings
    await expect(page.getByRole('heading', { name: 'Props Extraction' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Binding Value' })).toBeVisible()
    await expect(page.getByRole('heading', { name: /initial.*false/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: /Hover.*Press/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Variants' })).toBeVisible()
    await expect(page.getByRole('heading', { name: /While In View/i })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Reactive Binding' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Mount / Unmount' })).toBeVisible()
  })

  test('box elements are rendered', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    await expect(page.getByText('Fade In')).toBeVisible()
    await expect(page.getByText('Slide In')).toBeVisible()
    await expect(page.getByText('No Entry Animation')).toBeVisible()
    await expect(page.getByText('Hover / Press me')).toBeVisible()
    await expect(page.getByText('Variant Slide')).toBeVisible()
  })

  test('reactive binding buttons update x value', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    // Initially x is 0
    const reactiveBox = page.getByText(/x: 0/)
    await expect(reactiveBox).toBeVisible()

    // Click Right
    await page.getByRole('button', { name: /Right/ }).click()
    await page.waitForTimeout(300)

    await expect(page.getByText(/x: 80/)).toBeVisible()
  })

  test('reactive binding reset button resets x to 0', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    // Move right
    await page.getByRole('button', { name: /Right/ }).click()
    await page.waitForTimeout(300)
    await expect(page.getByText(/x: 80/)).toBeVisible()

    // Reset
    await page.getByRole('button', { name: 'Reset' }).click()
    await page.waitForTimeout(300)
    await expect(page.getByText(/x: 0/)).toBeVisible()
  })

  test('reactive binding left button decrements x', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    await page.getByRole('button', { name: /Left/ }).click()
    await page.waitForTimeout(300)

    await expect(page.getByText(/x: -80/)).toBeVisible()
  })

  test('mount/unmount toggle shows and hides element', async ({ page }) => {
    await page.goto('/directive')
    await page.waitForLoadState('networkidle')

    // Initially visible (isVisible = true)
    await expect(page.getByText('Toggle me')).toBeVisible()

    const toggleBtn = page.getByRole('button').filter({ hasText: /Hide|Show/ })
    await expect(toggleBtn).toHaveText('Hide')

    await toggleBtn.click()
    await page.waitForTimeout(600)

    await expect(page.getByText('Toggle me')).not.toBeVisible()
    await expect(toggleBtn).toHaveText('Show')

    // Show again
    await toggleBtn.click()
    await page.waitForTimeout(600)
    await expect(page.getByText('Toggle me')).toBeVisible()
  })
})

test.describe('Directive - Presets', () => {
  test('page loads with preset heading', async ({ page }) => {
    await page.goto('/directive/preset')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { level: 1, name: 'Preset Directives' })).toBeVisible()
  })

  test('all preset directive elements are visible', async ({ page }) => {
    await page.goto('/directive/preset')
    await page.waitForLoadState('networkidle')

    await expect(page.getByTestId('fade-in')).toBeVisible()
    await expect(page.getByTestId('slide-up')).toBeVisible()
    await expect(page.getByTestId('scale-in')).toBeVisible()
    await expect(page.getByTestId('override')).toBeVisible()
  })

  test('preset section headings are visible', async ({ page }) => {
    await page.goto('/directive/preset')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('heading', { name: 'v-fade-in' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'v-slide-up' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'v-scale-in' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Override Preset' })).toBeVisible()
  })

  test('toggle button shows and hides target', async ({ page }) => {
    await page.goto('/directive/preset')
    await page.waitForLoadState('networkidle')

    // Initially visible (show = true)
    await expect(page.getByTestId('toggle-target')).toBeVisible()
    await expect(page.getByTestId('toggle-btn')).toHaveText('Hide')

    await page.getByTestId('toggle-btn').click()
    await page.waitForTimeout(400)

    await expect(page.getByTestId('toggle-target')).not.toBeVisible()
    await expect(page.getByTestId('toggle-btn')).toHaveText('Show')

    // Show again
    await page.getByTestId('toggle-btn').click()
    await page.waitForTimeout(400)
    await expect(page.getByTestId('toggle-target')).toBeVisible()
  })
})
