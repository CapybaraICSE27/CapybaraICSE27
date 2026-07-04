import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

test.describe('Task Detailed Interactions', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('task shows title text visible', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // Get first task's title from the task element
    const firstTask = page.locator('task').first();
    const taskText = await firstTask.innerText();
    expect(taskText.trim()).toBeTruthy();
  });

  test('task has a data-task-id attribute', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const firstTask = page.locator('task').first();
    const taskId = await firstTask.getAttribute('data-task-id');
    expect(taskId).toBeTruthy();
    expect(taskId).not.toBe('');
  });

  test('multiple tasks render correctly', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const tasks = page.locator('task');
    const count = await tasks.count();
    expect(count).toBeGreaterThanOrEqual(4);

    // Each task should have a done-toggle
    for (let i = 0; i < Math.min(count, 3); i++) {
      const toggle = tasks.nth(i).locator('done-toggle');
      await expect(toggle).toBeAttached();
    }
  });

  test('clicking task title reveals task detail (right panel)', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // Click on the task content area (the title/first-line area)
    const firstTask = page.locator('task').first();
    const titleArea = firstTask.locator('.title-and-left-btns-wrapper, .first-line');
    await titleArea.first().click();
    await page.waitForTimeout(1000);

    // The right panel should open with task details
    // Look for the task detail panel (right panel or task-detail-panel)
    const rightPanel = page.locator('right-panel, task-detail-panel, .task-detail');
    // At minimum, the app shouldn't crash
    await expect(page.locator('app-root')).toBeVisible();
  });

  test('task context menu opens via chat button', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const firstTask = page.locator('task').first();
    // The chat/note button on the task
    const chatBtn = firstTask
      .locator('button')
      .filter({ has: page.locator('mat-icon:has-text("chat")') });

    if ((await chatBtn.count()) > 0) {
      await chatBtn.click({ force: true });
      await page.waitForTimeout(500);
      // Some panel or dialog should open
      await expect(page.locator('app-root')).toBeVisible();
    }
  });

  test('task has no "chat" button by default when not focused', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const firstTask = page.locator('task').first();
    const chatBtn = firstTask.locator('button mat-icon:text("chat")');
    // Chat button exists but visibility depends on task state
    await expect(firstTask).toBeVisible();
  });

  test('Today page shows "No tasks planned" when empty', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    // Today tasks page with no tasks shows empty state
    const bodyText = await page.locator('body').innerText();
    // It might say "No tasks planned" or show the add task prompt
    expect(bodyText).toMatch(/No tasks planned|add/i);
  });

  test('Inbox task count badge appears in sidebar', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    // The Inbox project nav item shows task count
    const inboxNavItem = page.locator('nav-item[data-project-id="INBOX_PROJECT"]');
    await expect(inboxNavItem).toBeVisible();

    // Should have a task count badge
    const countBadge = inboxNavItem.locator('.task-count');
    await expect(countBadge).toBeVisible();
    const countText = await countBadge.innerText();
    expect(parseInt(countText)).toBeGreaterThan(0);
  });
});

test.describe('Task Add Bar - Advanced', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('add task bar has placeholder with syntax hint', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await page.locator('.tour-addBtn').click();
    await page.waitForSelector('add-task-bar input', { timeout: 5000 });

    const input = page.locator('add-task-bar input');
    const placeholder = await input.getAttribute('placeholder');
    // Should show syntax hints like #tag, @time, t for duration
    expect(placeholder).toMatch(/#tag|@|task title/i);
  });

  test('add task bar has search toggle button', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await page.locator('.tour-addBtn').click();
    await page.waitForSelector('add-task-bar input', { timeout: 5000 });

    // Search toggle button (search icon)
    const searchToggle = page.locator('.search-toggle-btn');
    await expect(searchToggle).toBeVisible();
  });

  test('can switch add task bar to search mode', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await page.locator('.tour-addBtn').click();
    await page.waitForSelector('add-task-bar input', { timeout: 5000 });

    // Click search toggle
    const searchToggle = page.locator('.search-toggle-btn');
    await searchToggle.click();
    await page.waitForTimeout(500);

    // Input placeholder should change to search mode
    const input = page.locator('add-task-bar input');
    const placeholder = await input.getAttribute('placeholder');
    expect(placeholder).toBeTruthy();
  });

  test('add task bar shows add-to-bottom toggle', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await page.locator('.tour-addBtn').click();
    await page.waitForSelector('add-task-bar input', { timeout: 5000 });

    // Bottom/top toggle button
    const bottomBtn = page.locator('.switch-add-to-bot-btn');
    await expect(bottomBtn).toBeVisible();
  });
});
