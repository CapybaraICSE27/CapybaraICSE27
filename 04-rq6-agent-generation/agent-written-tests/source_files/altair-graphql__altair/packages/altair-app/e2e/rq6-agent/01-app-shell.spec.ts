import { test, expect } from '@playwright/test';

test.describe('App Shell – initial load', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for the Angular app to be ready (loading screen disappears)
    await expect(page.locator('.app-side-menu')).toBeVisible({ timeout: 20000 });
  });

  test('renders the Altair logo in the header', async ({ page }) => {
    await expect(page.locator('.header__logo')).toBeVisible();
  });

  test('shows the URL input box with placeholder', async ({ page }) => {
    const urlInput = page.locator('[track-id="set_url"]').first();
    await expect(urlInput).toBeVisible();
    await expect(urlInput).toHaveAttribute('placeholder', 'Enter URL');
  });

  test('shows HTTP method button defaulting to POST', async ({ page }) => {
    const methodBtn = page.locator('[track-id="http_verb"]').first();
    await expect(methodBtn).toBeVisible();
    await expect(methodBtn).toContainText('POST');
  });

  test('shows the Send Request button', async ({ page }) => {
    // When there is only one query operation, track-id is "set_request"
    const sendBtn = page.locator('[track-id="set_request"]').first();
    await expect(sendBtn).toBeVisible();
    await expect(sendBtn).toContainText('Send Request');
  });

  test('shows side menu with all primary actions', async ({ page }) => {
    await expect(page.locator('[track-id="show_set_headers"]')).toBeVisible();
    await expect(page.locator('[track-id="show_history"]')).toBeVisible();
  });

  test('shows the window tab bar with one default tab', async ({ page }) => {
    const tabList = page.locator('.window-switcher__list');
    await expect(tabList).toBeVisible();
    const items = tabList.locator('.window-switcher__item');
    await expect(items.first()).toBeVisible();
  });

  test('shows "Docs" button in the URL box area', async ({ page }) => {
    const docsBtn = page.locator('[track-id="show_docs"]').first();
    await expect(docsBtn).toBeVisible();
    await expect(docsBtn).toContainText('Docs');
  });

  test('shows the query editor tab area', async ({ page }) => {
    await expect(page.locator('.main-view-tabs').first()).toBeVisible();
  });

  test('result pane shows empty-state placeholder text', async ({ page }) => {
    await expect(page.locator('.query-result__none')).toBeVisible();
    await expect(page.getByText('Ezio my friend, how may I be of service?')).toBeVisible();
  });
});
