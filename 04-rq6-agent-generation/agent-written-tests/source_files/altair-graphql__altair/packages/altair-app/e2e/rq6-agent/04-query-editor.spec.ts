import { test, expect } from '@playwright/test';

test.describe('Query editor tabs and interactions', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  test('shows Query tab by default (active)', async ({ page }) => {
    // Use getByRole('tab') to avoid strict mode issues with getByText
    const queryTab = page.getByRole('tab', { name: 'Query' });
    await expect(queryTab).toBeVisible();
    await expect(queryTab).toHaveAttribute('aria-selected', 'true');
  });

  test('shows Pre-request tab in query editor', async ({ page }) => {
    const preRequestTab = page.getByRole('tab', { name: 'Pre-request' });
    await expect(preRequestTab).toBeVisible();
  });

  test('shows Post-request tab in query editor', async ({ page }) => {
    const postRequestTab = page.getByRole('tab', { name: 'Post-request' });
    await expect(postRequestTab).toBeVisible();
  });

  test('shows Auth tab in query editor', async ({ page }) => {
    const authTab = page.getByRole('tab', { name: 'Auth' });
    await expect(authTab).toBeVisible();
  });

  test('can navigate to Pre-request tab', async ({ page }) => {
    await page.getByRole('tab', { name: 'Pre-request' }).click();
    // After click, we should see the pre-request editor content area
    await expect(page.locator('app-pre-request-editor')).toBeVisible({ timeout: 5000 });
  });

  test('can navigate to Post-request tab', async ({ page }) => {
    await page.getByRole('tab', { name: 'Post-request' }).click();
    await expect(page.locator('app-post-request-editor')).toBeVisible({ timeout: 5000 });
  });

  test('can navigate to Auth tab', async ({ page }) => {
    await page.getByRole('tab', { name: 'Auth' }).click();
    // Auth tab shows the authorization editor component
    await expect(page.locator('app-authorization-editor')).toBeVisible({ timeout: 5000 });
  });

  test('Auth tab shows authorization type selector', async ({ page }) => {
    await page.getByRole('tab', { name: 'Auth' }).click();
    // Authorization editor has a type dropdown
    await expect(page.locator('app-authorization-editor nz-select')).toBeVisible({ timeout: 5000 });
  });

  test('Variables section toggle works', async ({ page }) => {
    const variablesToggle = page.locator('[track-id="toggle_variables"]');
    await expect(variablesToggle).toBeVisible();
    await variablesToggle.click();
    await expect(page.locator('.variables-editor-container')).toHaveClass(/show-variables/);
  });

  test('Variables section can be toggled closed again', async ({ page }) => {
    const variablesToggle = page.locator('[track-id="toggle_variables"]');
    // Open it
    await variablesToggle.click();
    await expect(page.locator('.variables-editor-container')).toHaveClass(/show-variables/);
    // Close it
    await variablesToggle.click();
    await expect(page.locator('.variables-editor-container')).not.toHaveClass(/show-variables/);
  });

  test('Query editor CodeMirror is present', async ({ page }) => {
    const editor = page.locator('app-query-editor .query-editor__input');
    await expect(editor).toBeVisible();
  });

  test('can switch back to Query tab from Pre-request', async ({ page }) => {
    // Go to Pre-request
    await page.getByRole('tab', { name: 'Pre-request' }).click();
    await expect(page.locator('app-pre-request-editor')).toBeVisible({ timeout: 5000 });

    // Go back to Query
    await page.getByRole('tab', { name: 'Query' }).first().click();
    await expect(page.locator('app-query-editor .query-editor__input')).toBeVisible({ timeout: 5000 });
  });
});
