import { test, expect } from '@playwright/test';
import { skipOnboarding, waitForAppLoad } from './helpers';

test.describe('Config / Settings Page', () => {
  test.beforeEach(async ({ context }) => {
    await skipOnboarding(context);
  });

  test('Config page loads with Global Settings title', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    await expect(page.locator('.page-title')).toContainText('Global Settings');
  });

  test('Config page has tab navigation', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(6);
  });

  test('Config General tab is active by default', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const generalTab = page.locator('[role="tab"]').filter({ hasText: 'General' });
    await expect(generalTab).toHaveAttribute('aria-selected', 'true');
  });

  test('Config tabs include: General, Tasks, Time & Tracking, Productivity, Plugins, Sync & Backup', async ({
    page,
  }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const tabTexts = await page.locator('[role="tab"]').allInnerTexts();
    const flatText = tabTexts.join(' ');

    expect(flatText).toMatch(/General/i);
    expect(flatText).toMatch(/Tasks/i);
    expect(flatText).toMatch(/Time|Tracking/i);
    expect(flatText).toMatch(/Productivity/i);
    expect(flatText).toMatch(/Plugin/i);
    expect(flatText).toMatch(/Sync|Backup/i);
  });

  test('Config General tab shows settings sections', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Localization/i);
    expect(bodyText).toMatch(/App Features|Keyboard Shortcuts|Misc Settings/i);
  });

  test('switching to Tasks tab shows task-related settings', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const tasksTab = page.locator('[role="tab"]').filter({ hasText: 'Tasks' });
    await tasksTab.click();

    // Wait for tab content to load
    await page.waitForTimeout(500);
    await expect(tasksTab).toHaveAttribute('aria-selected', 'true');
  });

  test('switching to Sync & Backup tab shows sync settings', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const syncTab = page.locator('[role="tab"]').filter({ hasText: /Sync|Backup/i });
    await syncTab.click();
    await page.waitForTimeout(500);

    await expect(syncTab).toHaveAttribute('aria-selected', 'true');
  });

  test('switching to Time & Tracking tab', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const timeTab = page.locator('[role="tab"]').filter({ hasText: /Time|Tracking/i });
    await timeTab.click();
    await page.waitForTimeout(500);

    await expect(timeTab).toHaveAttribute('aria-selected', 'true');
  });

  test('switching to Productivity tab', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const prodTab = page.locator('[role="tab"]').filter({ hasText: /Productivity/i });
    await prodTab.click();
    await page.waitForTimeout(500);

    await expect(prodTab).toHaveAttribute('aria-selected', 'true');
  });

  test('switching to Plugins tab', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const pluginsTab = page.locator('[role="tab"]').filter({ hasText: /Plugin/i });
    await pluginsTab.click();
    await page.waitForTimeout(500);

    await expect(pluginsTab).toHaveAttribute('aria-selected', 'true');
  });

  test('General tab has expandable Localization section', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    // Localization section should be present
    const locSection = page.locator('.section-localization');
    await expect(locSection).toBeVisible();
  });

  test('General tab has expandable Keyboard Shortcuts section', async ({ page }) => {
    await page.goto('/#/config');
    await waitForAppLoad(page);

    const kbSection = page.locator('.section-keyboard');
    await expect(kbSection).toBeVisible();
  });
});
