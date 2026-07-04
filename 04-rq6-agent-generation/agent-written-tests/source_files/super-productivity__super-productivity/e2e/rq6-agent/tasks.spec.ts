import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad, openAddTaskBar, addTask } from './helpers';

test.describe('Task Management', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Inbox page shows example tasks', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const tasks = page.locator('task');
    await expect(tasks).toHaveCount(4, { timeout: 10000 });

    // Check known example task titles
    await expect(
      page.locator('task').filter({ hasText: 'Create your first project' }),
    ).toBeVisible();
    await expect(page.locator('task').filter({ hasText: 'Set up Sync' })).toBeVisible();
    await expect(
      page.locator('task').filter({ hasText: 'Learn the keyboard shortcuts' }),
    ).toBeVisible();
    await expect(page.locator('task').filter({ hasText: 'Go further' })).toBeVisible();
  });

  test('task items display done-toggle checkbox', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const firstTask = page.locator('task').first();
    await expect(firstTask).toBeVisible();

    // The done-toggle is an aria role="checkbox" element
    const doneToggle = firstTask.locator('done-toggle');
    await expect(doneToggle).toBeVisible();
    await expect(doneToggle).toHaveAttribute('role', 'checkbox');
    await expect(doneToggle).toHaveAttribute('aria-label', 'Toggle completion status');
  });

  test('add task bar opens when clicking add button', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await openAddTaskBar(page);

    const input = page.locator('add-task-bar input');
    await expect(input).toBeVisible();
    await expect(input).toBeFocused();

    // Check placeholder text
    const placeholder = await input.getAttribute('placeholder');
    expect(placeholder).toContain('task title');
  });

  test('can add a new task to Inbox', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const initialCount = await page.locator('task').count();

    await addTask(page, 'E2E Test Task Created');

    // Wait for the new task to appear
    await expect(page.locator('task')).toHaveCount(initialCount + 1, { timeout: 10000 });
    await expect(
      page.locator('task').filter({ hasText: 'E2E Test Task Created' }),
    ).toBeVisible();
  });

  test('close add task bar with Escape key', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await openAddTaskBar(page);
    const input = page.locator('add-task-bar input');
    await expect(input).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(input).toBeHidden({ timeout: 5000 });
  });

  test('can add a task to Today page', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const initialCount = await page.locator('task').count();

    await addTask(page, 'E2E Today Task');

    // Wait for new task to appear
    await expect(page.locator('task')).toHaveCount(initialCount + 1, { timeout: 10000 });
    await expect(
      page.locator('task').filter({ hasText: 'E2E Today Task' }),
    ).toBeVisible();
  });

  test('header shows add button (.tour-addBtn)', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    const addBtn = page.locator('.tour-addBtn');
    await expect(addBtn).toBeVisible();
  });

  test('header shows play/start timer button', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // The play button (start timer) renders as a mini-fab
    const playBtn = page.locator('play-button');
    await expect(playBtn).toBeVisible();
  });

  test('task has a title displayed', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // First task title text should be visible
    const firstTask = page.locator('task').first();
    const taskText = await firstTask.innerText();
    expect(taskText.trim().length).toBeGreaterThan(0);
  });

  test('done-toggle initial state is not checked', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // First task's done-toggle should have aria-checked=false
    const firstToggle = page.locator('task done-toggle').first();
    await expect(firstToggle).toHaveAttribute('aria-checked', 'false');
  });

  test('toggle task done marks it as complete', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    // Get all tasks and pick the first one by data-task-id
    const firstTask = page.locator('task').first();
    await firstTask.waitFor({ state: 'visible' });
    const taskId = await firstTask.getAttribute('data-task-id');
    expect(taskId).toBeTruthy();

    // Get the done-toggle on that specific task
    const doneToggle = firstTask.locator('done-toggle');
    await expect(doneToggle).toHaveAttribute('aria-checked', 'false');

    // Click to mark done
    await doneToggle.click();
    await page.waitForTimeout(1000);

    // The task may have moved (e.g., to a done section at the bottom).
    // Re-query the toggle by specific task id to get the actual element.
    const specificTaskToggle = page.locator(`task[data-task-id="${taskId}"] done-toggle`);
    await expect(specificTaskToggle).toHaveAttribute('aria-checked', 'true', {
      timeout: 8000,
    });
  });
});
