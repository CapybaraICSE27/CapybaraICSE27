import { test, expect } from '@playwright/test';
import { LS_KEYS, waitForAppLoad } from './helpers';

test.describe('Onboarding', () => {
  test('onboarding preset selection shows on fresh load', async ({ page }) => {
    // Fresh context (no localStorage) should show the onboarding
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });
  });

  test('onboarding dialog shows setup options', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });

    // Should have preset option cards
    const presetCards = onboarding.locator('.preset-card');
    const count = await presetCards.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('onboarding has a title about setup', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });

    const title = onboarding.locator('h1');
    await expect(title).toContainText('Super Productivity');
  });

  test('onboarding shows "Simple Todo List" preset', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Simple Todo List/i);
  });

  test('onboarding shows "Time Tracker" preset', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Time Tracker/i);
  });

  test('onboarding shows "Productivity Suite" preset', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });

    const bodyText = await page.locator('body').innerText();
    expect(bodyText).toMatch(/Productivity Suite/i);
  });

  test('selecting a preset dismisses the onboarding', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeVisible({ timeout: 10000 });

    // Click the first preset card (Simple Todo List)
    const firstPreset = onboarding.locator('.preset-card').first();
    await firstPreset.click();

    // Wait for onboarding to be dismissed
    await expect(onboarding).toBeHidden({ timeout: 10000 });
  });

  test('skipping onboarding via localStorage shows app directly', async ({
    context,
    page,
  }) => {
    // Set the localStorage keys to skip onboarding
    await context.addInitScript(
      ({ keys }: { keys: typeof LS_KEYS }) => {
        localStorage.setItem(keys.ONBOARDING_PRESET_DONE, 'true');
        localStorage.setItem(keys.ONBOARDING_HINTS_DONE, 'true');
      },
      { keys: LS_KEYS },
    );

    await page.goto('/');
    await waitForAppLoad(page);

    // Onboarding should not appear
    const onboarding = page.locator('onboarding-preset-selection');
    await expect(onboarding).toBeHidden();

    // App should show main content
    await expect(page.locator('magic-side-nav')).toBeVisible();
  });

  test('app body has is-onboarding class during onboarding', async ({ page }) => {
    await page.goto('/');
    await waitForAppLoad(page);

    const appContainer = page.locator('.app-container.is-onboarding');
    await expect(appContainer).toBeVisible({ timeout: 10000 });
  });
});
