/**
 * Settings page tests: view/edit toggle, profile fields.
 * Auth is bypassed via localStorage injection.
 */
import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers';

test.describe('Settings page', () => {
    test('settings page loads at /settings', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        await expect(page).toHaveURL(/\/settings/);
    });

    test('shows "My info" heading', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        await expect(page.getByText(/my info/i)).toBeVisible({
            timeout: 10_000,
        });
    });

    test('shows the user first name', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        // Default user is Jane Doe
        await expect(page.getByText('Jane')).toBeVisible({ timeout: 10_000 });
    });

    test('shows the user last name', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        await expect(page.getByText('Doe')).toBeVisible({ timeout: 10_000 });
    });

    test('shows the user email', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        await expect(page.getByText('janedoe@atomic.dev')).toBeVisible({
            timeout: 10_000,
        });
    });

    test('shows Change password button in view mode', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('button', { name: /change password/i })
        ).toBeVisible({ timeout: 10_000 });
    });

    test('shows Edit button to toggle edit mode', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');
        await expect(page.getByRole('button', { name: /edit/i })).toBeVisible({
            timeout: 10_000,
        });
    });

    test('clicking Edit reveals text input fields', async ({ page }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');

        await page.getByRole('button', { name: /edit/i }).click();

        // In edit mode, text inputs for first_name, last_name, email appear
        await expect(
            page.getByRole('textbox', { name: /first.name/i })
        ).toBeVisible({ timeout: 5_000 });
        await expect(
            page.getByRole('textbox', { name: /last.name/i })
        ).toBeVisible();
        await expect(
            page.getByRole('textbox', { name: /email/i })
        ).toBeVisible();
    });

    test('edit mode shows Show button to revert to view mode', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');

        await page.getByRole('button', { name: /edit/i }).click();
        // Button label changes to "Show" in edit mode
        await expect(page.getByRole('button', { name: /show/i })).toBeVisible({
            timeout: 5_000,
        });
    });

    test('clicking Show in edit mode returns to view mode', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/settings');
        await page.waitForLoadState('networkidle');

        await page.getByRole('button', { name: /edit/i }).click();
        await expect(
            page.getByRole('textbox', { name: /first.name/i })
        ).toBeVisible({ timeout: 5_000 });

        await page.getByRole('button', { name: /show/i }).click();
        // Back to view mode: text inputs should be gone
        await expect(
            page.getByRole('textbox', { name: /first.name/i })
        ).not.toBeVisible({ timeout: 5_000 });
    });

    test('settings page is reachable via user menu', async ({ page }) => {
        await gotoAuthenticated(page, '/');

        // Open user menu via the Profile button (aria-label from ra.auth.user_menu)
        await page.getByRole('button', { name: 'Profile' }).click();

        // Click "My info" menu item (ConfigurationMenu renders "My info")
        await page.getByRole('menuitem', { name: /my info/i }).click();
        await page.waitForURL(/\/settings/, { timeout: 10_000 });
        await expect(page).toHaveURL(/\/settings/);
    });
});
