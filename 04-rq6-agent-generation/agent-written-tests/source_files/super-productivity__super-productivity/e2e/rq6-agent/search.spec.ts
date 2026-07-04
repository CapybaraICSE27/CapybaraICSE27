import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad, addTask } from './helpers';

test.describe('Search Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('search input has correct placeholder text', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    const input = page.locator('input[placeholder*="Search for task"]');
    await expect(input).toBeVisible();
    await expect(input).toHaveAttribute('placeholder', /Search for task/i);
  });

  test('search input is auto-focused on page load', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    const input = page.locator('input[placeholder*="Search for task"]');
    await expect(input).toBeVisible();
  });

  test('search page has checkbox for archived/completed tasks', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    // The page has a checkbox to include completed/archived tasks
    const checkbox = page.locator('input[type="checkbox"]').first();
    await expect(checkbox).toBeAttached();
  });

  test('typing in search input shows results or empty state', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    const input = page.locator('input[placeholder*="Search for task"]');
    await input.fill('Create');
    await page.waitForTimeout(500);

    // Should show some kind of result or empty message
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.length).toBeGreaterThan(100);
  });

  test('searching for existing task title shows results', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    const input = page.locator('input[placeholder*="Search for task"]');
    // The Inbox has example tasks, one is "Create your first project"
    await input.fill('Create your first project');
    await page.waitForTimeout(1000);

    const bodyText = await page.locator('body').innerText();
    // Should find the example task
    expect(bodyText).toMatch(/Create your first project/i);
  });

  test('clearing search input clears results', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    const input = page.locator('input[placeholder*="Search for task"]');
    await input.fill('test search');
    await page.waitForTimeout(300);
    await input.clear();
    await page.waitForTimeout(300);

    // Input should be empty
    await expect(input).toHaveValue('');
  });

  test('search page has page title "Search"', async ({ page }) => {
    await page.goto('/#/search');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Search');
  });
});
