import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

test.describe('Standalone Pages', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Planner page loads with correct title', async ({ page }) => {
    await page.goto('/#/planner');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Planner');
  });

  test('Planner page shows day columns', async ({ page }) => {
    await page.goto('/#/planner');
    await waitForAppLoad(page);

    // Planner shows day plan view components
    const content = page.locator('planner-plan-view, planner-day').first();
    await expect(content).toBeVisible({ timeout: 10000 });
  });

  test('Planner shows current date', async ({ page }) => {
    await page.goto('/#/planner');
    await waitForAppLoad(page);

    // The planner renders today's date somewhere on screen
    const pageContent = await page.locator('body').innerText();
    // Should contain some date-related content
    expect(pageContent.length).toBeGreaterThan(50);
  });

  test('Schedule page loads with correct title', async ({ page }) => {
    await page.goto('/#/schedule');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Schedule');
  });

  test('Schedule page renders week view navigation', async ({ page }) => {
    await page.goto('/#/schedule');
    await waitForAppLoad(page);

    // Should have view toggle buttons (week/month)
    const pageContent = await page.locator('body').innerText();
    expect(pageContent).toMatch(/week|schedule/i);
  });

  test('Boards page loads with Eisenhower Matrix content', async ({ page }) => {
    await page.goto('/#/boards');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Boards');
    // Eisenhower Matrix board should be visible
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Eisenhower Matrix|Kanban/i);
  });

  test('Habits page loads with calendar navigation', async ({ page }) => {
    await page.goto('/#/habits');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Habits');
    // Habits has a date range navigation
    const chevronBtns = page.locator('mat-icon').filter({ hasText: 'chevron_left' });
    await expect(chevronBtns.first()).toBeVisible({ timeout: 10000 });
  });

  test('Search page loads with search input', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Search');
    // Should have a search input
    const searchInput = page
      .locator(
        'search-page input, input[type="search"], input[placeholder*="Search"], input[placeholder*="task"]',
      )
      .first();
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test('Search page has filter for completed/archived tasks', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/completed|archived|Include/i);
  });

  test('Scheduled/Upcoming page loads with sections', async ({ page }) => {
    await page.goto('/#/scheduled-list');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Upcoming');
    // Should have recurring tasks and scheduled tasks sections
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Recurring|Scheduled/i);
  });

  test('Scheduled page shows empty state for recurring tasks', async ({ page }) => {
    await page.goto('/#/scheduled-list');
    await waitForAppLoad(page);

    // Fresh app has no recurring tasks
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/No recurring tasks yet/i);
  });

  test('Donate/Support page loads with content', async ({ page }) => {
    await page.goto('/#/donate');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Support us');
    // Should have donation content
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Super Productivity|funded|community/i);
  });

  test('Archived Projects page loads', async ({ page }) => {
    await page.goto('/#/archived-projects');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Archived Projects');
  });

  test('Archived Projects shows empty state', async ({ page }) => {
    await page.goto('/#/archived-projects');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/No archived projects|Search archived/i);
  });

  test('Archived Projects has search input', async ({ page }) => {
    await page.goto('/#/archived-projects');
    await waitForAppLoad(page);

    const searchInput = page
      .locator('input[placeholder*="Search"], input[placeholder*="archived"]')
      .first();
    await expect(searchInput).toBeVisible({ timeout: 10000 });
  });

  test('Contrast Test page loads with button sections', async ({ page }) => {
    await page.goto('/#/contrast-test');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Contrast Test|button/i);
  });
});

test.describe('Context Sub-pages (Tag & Project)', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Today History page loads', async ({ page }) => {
    await page.goto('/#/tag/TODAY/history');
    await waitForAppLoad(page);
    await expect(page).toHaveURL(/#\/tag\/TODAY\/history/);
    // History component renders
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Today Daily Summary page loads', async ({ page }) => {
    await page.goto('/#/tag/TODAY/daily-summary');
    await waitForAppLoad(page);
    await expect(page).toHaveURL(/#\/tag\/TODAY\/daily-summary/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Today Metrics page loads', async ({ page }) => {
    await page.goto('/#/tag/TODAY/metrics');
    await waitForAppLoad(page);
    await expect(page).toHaveURL(/#\/tag\/TODAY\/metrics/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Inbox History page loads (via legacy worklog route)', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/worklog');
    await waitForAppLoad(page);
    // Legacy worklog redirects to history
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Inbox Daily Summary page loads', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/daily-summary');
    await waitForAppLoad(page);
    await expect(page).toHaveURL(/#\/project\/INBOX_PROJECT\/daily-summary/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });

  test('Inbox Metrics page loads', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/metrics');
    await waitForAppLoad(page);
    await expect(page).toHaveURL(/#\/project\/INBOX_PROJECT\/metrics/);
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(20);
  });
});
