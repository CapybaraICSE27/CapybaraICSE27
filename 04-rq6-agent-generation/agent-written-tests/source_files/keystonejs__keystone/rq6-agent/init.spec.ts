/**
 * Tests for /init page behaviour after the first user has been created.
 *
 * After user creation, the server returns 302 with an empty Location header,
 * so the browser stays at the /init URL indefinitely.  React renders the
 * page without the "Create your first user" form.
 */

import { test, expect } from '@playwright/test'

test.describe('/init page (post-initialisation)', () => {
  test('Create First User form is not shown once users exist', async ({ page }) => {
    await page.goto('/init')
    // Page loads (server keeps browser at /init after 302 with empty Location)
    await page.waitForLoadState('networkidle', { timeout: 15_000 })
    await expect(
      page.getByRole('heading', { name: /create your first user/i })
    ).not.toBeVisible()
  })
})
