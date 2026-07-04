import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

test.describe('Navigation & Sidebar', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('loads and redirects to Today tasks page', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);
    // Should redirect to today's tasks
    await expect(page).toHaveURL(/#\/tag\/TODAY\/tasks/);
    await expect(page.locator('.page-title')).toContainText('Today');
  });

  test('sidebar is visible with main navigation items', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const nav = page.locator('magic-side-nav nav');
    await expect(nav).toBeVisible();

    // Check key nav items are present
    await expect(page.locator('nav-item').filter({ hasText: 'Today' })).toBeVisible();
    await expect(page.locator('nav-item').filter({ hasText: 'Inbox' })).toBeVisible();
  });

  test('sidebar shows Planner, Schedule, Boards, Habits links', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await expect(page.locator('a[href="#/planner"]')).toBeVisible();
    await expect(page.locator('a[href="#/schedule"]')).toBeVisible();
    await expect(page.locator('a[href="#/boards"]')).toBeVisible();
    await expect(page.locator('a[href="#/habits"]')).toBeVisible();
  });

  test('sidebar shows Search, Upcoming, Donate, Settings links', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await expect(page.locator('a[href="#/search"]')).toBeVisible();
    await expect(page.locator('a[href="#/scheduled-list"]')).toBeVisible();
    await expect(page.locator('a[href="#/donate"]')).toBeVisible();
    await expect(page.locator('a[href="#/config"]')).toBeVisible();
  });

  test('navigate to Planner via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/planner"]').click();
    await expect(page).toHaveURL(/#\/planner/);
    await expect(page.locator('.page-title')).toContainText('Planner');
  });

  test('navigate to Schedule via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/schedule"]').click();
    await expect(page).toHaveURL(/#\/schedule/);
    await expect(page.locator('.page-title')).toContainText('Schedule');
  });

  test('navigate to Boards via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/boards"]').click();
    await expect(page).toHaveURL(/#\/boards/);
    await expect(page.locator('.page-title')).toContainText('Boards');
  });

  test('navigate to Habits via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/habits"]').click();
    await expect(page).toHaveURL(/#\/habits/);
    await expect(page.locator('.page-title')).toContainText('Habits');
  });

  test('navigate to Search via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/search"]').click();
    await expect(page).toHaveURL(/#\/search/);
    await expect(page.locator('.page-title')).toContainText('Search');
  });

  test('navigate to Upcoming/Scheduled List via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/scheduled-list"]').click();
    await expect(page).toHaveURL(/#\/scheduled-list/);
    await expect(page.locator('.page-title')).toContainText('Upcoming');
  });

  test('navigate to Settings via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/config"]').click();
    await expect(page).toHaveURL(/#\/config/);
    await expect(page.locator('.page-title')).toContainText('Global Settings');
  });

  test('navigate to Donate page via sidebar link', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    await page.locator('a[href="#/donate"]').click();
    await expect(page).toHaveURL(/#\/donate/);
    await expect(page.locator('.page-title')).toContainText('Support us');
  });

  test('sidebar Projects section is collapsible', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    // Find the Projects expand/collapse button
    const projectsBtn = page.locator('nav button').filter({ hasText: 'Projects' });
    await expect(projectsBtn).toBeVisible();
    // It should be clickable
    await projectsBtn.click();
    await page.waitForTimeout(500);
    // Click again to toggle back
    await projectsBtn.click();
  });

  test('sidebar Tags section is collapsible', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const tagsBtn = page.locator('nav button').filter({ hasText: 'Tags' });
    await expect(tagsBtn).toBeVisible();
    await tagsBtn.click();
    await page.waitForTimeout(500);
    await tagsBtn.click();
  });

  test('sidebar compact mode toggle button is visible', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);

    const modeToggle = page.locator('magic-side-nav .mode-toggle');
    await expect(modeToggle).toBeVisible();
    // It should have aria-label about switching modes
    const ariaLabel = await modeToggle.getAttribute('aria-label');
    expect(ariaLabel).toMatch(/compact|full|mode/i);
  });

  test('navigate to Inbox project page', async ({ page }) => {
    await page.goto('/#/project/INBOX_PROJECT/tasks');
    await waitForAppLoad(page);

    await expect(page).toHaveURL(/#\/project\/INBOX_PROJECT\/tasks/);
    await expect(page.locator('.page-title')).toContainText('Inbox');
  });

  test('direct URL navigation to Today works', async ({ page }) => {
    await page.goto('/#/tag/TODAY/tasks');
    await waitForAppLoad(page);
    await expect(page.locator('.page-title')).toContainText('Today');
  });

  test('wildcard route redirects to default start page', async ({ page }) => {
    await page.goto('/#/nonexistent-route-xyz');
    await waitForAppLoad(page);
    // Should redirect to some valid default page (Today)
    await expect(page).toHaveURL(/#\/(tag|project)\//);
  });
});
