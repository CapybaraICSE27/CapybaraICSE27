import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad, openAddTaskBar } from './helpers';

test.describe('Main Header Interactions', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('page title is displayed in header', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const pageTitle = page.locator('.page-title');
    await expect(pageTitle).toBeVisible();
    await expect(pageTitle).toContainText('Inbox');
  });

  test('page title changes on navigation', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Today');

    await page.goto('/#/planner');
    await waitForAppLoad(page);
    await expect(page.locator('.page-title')).toContainText('Planner');
  });

  test('add task button opens task bar', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await openAddTaskBar(page);
    const bar = page.locator('add-task-bar');
    await expect(bar).toBeVisible();
  });

  test('sync button is visible in header', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // The sync button shows sync_disabled icon (since sync is not configured)
    const syncBtn = page.locator('button.sync-btn');
    await expect(syncBtn).toBeVisible();
  });

  test('focus button is visible in header', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // Focus button component
    const focusBtn = page.locator('focus-button');
    await expect(focusBtn).toBeVisible();
  });

  test('filter button is visible on task page header', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // Filter button (filter_list icon)
    const filterBtn = page
      .locator('button')
      .filter({ has: page.locator('mat-icon:has-text("filter_list")') });
    await expect(filterBtn.first()).toBeVisible();
  });

  test('clicking filter button opens filter menu', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const filterBtn = page.locator('.task-filter-btn');
    await expect(filterBtn).toBeVisible();
    await filterBtn.click();
    await page.waitForTimeout(500);

    // Should open a menu or panel
    const menu = page.locator('.mat-mdc-menu-panel');
    await expect(menu).toBeVisible({ timeout: 5000 });
  });

  test('header more_vert button opens context menu', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // The .project-settings-btn is the more_vert on the page title
    const moreBtn = page.locator('.project-settings-btn');
    await expect(moreBtn).toBeVisible();
    await moreBtn.click();
    await page.waitForTimeout(500);

    // Should open menu
    const menu = page.locator('.mat-mdc-menu-panel');
    await expect(menu).toBeVisible({ timeout: 5000 });
  });

  test('add task bar input accepts text', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await openAddTaskBar(page);
    const input = page.locator('add-task-bar input');
    await input.fill('Test Task Title');
    await expect(input).toHaveValue('Test Task Title');
  });

  test('add task bar shows submit button when text is entered', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await openAddTaskBar(page);
    const input = page.locator('add-task-bar input');
    await input.fill('My Task');

    // Submit button (e2e-add-task-submit class) appears when text is entered
    const submitBtn = page.locator('.e2e-add-task-submit');
    await expect(submitBtn).toBeVisible({ timeout: 5000 });
  });

  test('closing add task bar with backdrop click', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await openAddTaskBar(page);
    await expect(page.locator('add-task-bar')).toBeVisible();

    // Click the backdrop
    const backdrop = page.locator('.backdrop');
    await expect(backdrop).toBeVisible({ timeout: 5000 });
    await backdrop.click();

    // Bar should close
    await expect(page.locator('add-task-bar')).toBeHidden({ timeout: 5000 });
  });
});

test.describe('Play Button / Timer', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('play button is visible', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const playBtn = page.locator('play-button');
    await expect(playBtn).toBeVisible();
  });

  test('play button has play_arrow icon when no task running', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // When no task is active, should show play_arrow
    const playIcon = page
      .locator('play-button mat-icon')
      .filter({ hasText: 'play_arrow' });
    await expect(playIcon).toBeAttached();
  });
});
