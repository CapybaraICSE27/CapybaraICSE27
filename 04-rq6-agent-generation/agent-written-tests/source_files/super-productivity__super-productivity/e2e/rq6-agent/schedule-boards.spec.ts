import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

test.describe('Schedule Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Schedule page has schedule-week component', async ({ page }) => {
    await page.goto('/#/schedule');
    await waitForAppLoad(page);

    const scheduleWeek = page.locator('schedule-week');
    await expect(scheduleWeek).toBeVisible({ timeout: 10000 });
  });

  test('Schedule page shows week navigation', async ({ page }) => {
    await page.goto('/#/schedule');
    await waitForAppLoad(page);

    // Should have navigation arrows for prev/next week
    const chevronLeft = page.locator('mat-icon').filter({ hasText: 'chevron_left' });
    await expect(chevronLeft.first()).toBeVisible({ timeout: 10000 });
  });

  test('Schedule page shows current week indicator', async ({ page }) => {
    await page.goto('/#/schedule');
    await waitForAppLoad(page);

    // Should display week number or date range
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Week|Jun|2026/i);
  });

  test('Schedule page has view toggle (week/month)', async ({ page }) => {
    await page.goto('/#/schedule');
    await waitForAppLoad(page);

    // Look for view toggle buttons
    const viewBtns = page
      .locator('mat-icon')
      .filter({ hasText: /view_week|calendar_month/ });
    await expect(viewBtns.first()).toBeAttached();
  });
});

test.describe('Boards Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Boards page shows Eisenhower Matrix', async ({ page }) => {
    await page.goto('/#/boards');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Eisenhower Matrix/i);
  });

  test('Boards page has Kanban board options', async ({ page }) => {
    await page.goto('/#/boards');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Kanban|add_circle/i);
  });

  test('Boards page has add board button', async ({ page }) => {
    await page.goto('/#/boards');
    await waitForAppLoad(page);

    // Add circle icon for creating new board/tag
    const addCircle = page.locator('mat-icon').filter({ hasText: 'add_circle' });
    await expect(addCircle.first()).toBeAttached();
  });
});

test.describe('Habits Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Habits page has habit-tracker component', async ({ page }) => {
    await page.goto('/#/habits');
    await waitForAppLoad(page);

    const habitTracker = page.locator('habit-tracker');
    await expect(habitTracker).toBeVisible({ timeout: 10000 });
  });

  test('Habits page has previous week navigation', async ({ page }) => {
    await page.goto('/#/habits');
    await waitForAppLoad(page);

    const prevBtn = page.locator('mat-icon:has-text("chevron_left")').first();
    await expect(prevBtn).toBeVisible({ timeout: 10000 });
  });

  test('Habits page has next week navigation', async ({ page }) => {
    await page.goto('/#/habits');
    await waitForAppLoad(page);

    const nextBtn = page.locator('mat-icon:has-text("chevron_right")').first();
    await expect(nextBtn).toBeVisible({ timeout: 10000 });
  });

  test('Habits page shows day headers', async ({ page }) => {
    await page.goto('/#/habits');
    await waitForAppLoad(page);

    // Should show weekday names or day numbers
    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Mon|Tue|Wed|Thu|Fri|Sat|Sun/i);
  });

  test('Habits page navigation moves to previous week', async ({ page }) => {
    await page.goto('/#/habits');
    await waitForAppLoad(page);

    const bodyBefore = await page.locator('body').innerText();

    const prevBtn = page.locator('mat-icon:has-text("chevron_left")').first();
    await prevBtn.click();
    await page.waitForTimeout(500);

    const bodyAfter = await page.locator('body').innerText();
    // Content should have changed (different dates)
    expect(bodyAfter).not.toBe(bodyBefore);
  });
});

test.describe('Upcoming / Scheduled List Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Upcoming page has Recurring Tasks section', async ({ page }) => {
    await page.goto('/#/scheduled-list');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Recurring Tasks/i);
  });

  test('Upcoming page has Scheduled Tasks section', async ({ page }) => {
    await page.goto('/#/scheduled-list');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Scheduled Tasks/i);
  });

  test('Upcoming page shows empty state message for recurring', async ({ page }) => {
    await page.goto('/#/scheduled-list');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/No recurring tasks yet|side panel/i);
  });
});
