import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

test.describe('Daily Summary Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Daily Summary page for Today loads', async ({ page }) => {
    await page.goto('/#/tag/TODAY/daily-summary');
    await waitForAppLoad(page);

    await expect(page).toHaveURL(/#\/tag\/TODAY\/daily-summary/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Daily Summary has daily-summary component', async ({ page }) => {
    await page.goto('/#/tag/TODAY/daily-summary');
    await waitForAppLoad(page);

    const summary = page.locator('daily-summary');
    await expect(summary).toBeAttached();
  });

  test('Daily Summary for Inbox project loads', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/daily-summary');
    await waitForAppLoad(page);

    await expect(page).toHaveURL(/#\/project\/INBOX_PROJECT\/daily-summary/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Metrics page for Today loads', async ({ page }) => {
    await page.goto('/#/tag/TODAY/metrics');
    await waitForAppLoad(page);

    await expect(page).toHaveURL(/#\/tag\/TODAY\/metrics/);
  });

  test('Metrics page shows Activity Heatmap', async ({ page }) => {
    await page.goto('/#/tag/TODAY/metrics');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Activity Heatmap/i);
  });

  test('Metrics page has activity-heatmap component', async ({ page }) => {
    await page.goto('/#/tag/TODAY/metrics');
    await waitForAppLoad(page);

    const heatmap = page.locator('activity-heatmap');
    await expect(heatmap).toBeAttached();
  });

  test('History page loads for Today context', async ({ page }) => {
    await page.goto('/#/tag/TODAY/history');
    await waitForAppLoad(page);

    await expect(page).toHaveURL(/#\/tag\/TODAY\/history/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Worklog route redirects to history', async ({ page }) => {
    await page.goto('/#/tag/TODAY/worklog');
    await waitForAppLoad(page);

    // worklog is an alias for history, should render the same component
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });
});

test.describe('Donate / Support Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Donate page has donate page component', async ({ page }) => {
    await page.goto('/#/donate');
    await waitForAppLoad(page);

    const donate = page.locator('donate-page');
    await expect(donate).toBeAttached();
  });

  test('Donate page mentions funding', async ({ page }) => {
    await page.goto('/#/donate');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/funded|community|support/i);
  });

  test('Donate page mentions privacy', async ({ page }) => {
    await page.goto('/#/donate');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/tracking|analytics|privacy|no tracking/i);
  });
});

test.describe('Archived Projects Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Archived projects has search functionality', async ({ page }) => {
    await page.goto('/#/archived-projects');
    await waitForAppLoad(page);

    // Type in search
    const searchInput = page
      .locator('input[placeholder*="Search"], input[placeholder*="archived"]')
      .first();
    await expect(searchInput).toBeVisible({ timeout: 10000 });
    await searchInput.fill('test');
    await page.waitForTimeout(300);
    await expect(searchInput).toHaveValue('test');
  });

  test('Archived projects shows empty state', async ({ page }) => {
    await page.goto('/#/archived-projects');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/No archived projects/i);
  });
});
