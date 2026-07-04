/**
 * Dashboard page tests.
 * Auth is bypassed via localStorage injection.
 */
import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers';

test.describe('Dashboard', () => {
    test('loads and shows navigation header', async ({ page }) => {
        await gotoAuthenticated(page, '/');
        // Tabs in the app bar
        await expect(
            page.getByRole('tab', { name: /dashboard/i })
        ).toBeVisible();
        await expect(
            page.getByRole('tab', { name: /contacts/i })
        ).toBeVisible();
        await expect(
            page.getByRole('tab', { name: /companies/i })
        ).toBeVisible();
        await expect(page.getByRole('tab', { name: /deals/i })).toBeVisible();
    });

    test('shows Atomic CRM logo / title in header', async ({ page }) => {
        await gotoAuthenticated(page, '/');
        await expect(page.getByText('Atomic CRM')).toBeVisible();
    });

    test('navigating to Contacts tab goes to /contacts', async ({ page }) => {
        await gotoAuthenticated(page, '/');
        await page.getByRole('tab', { name: /contacts/i }).click();
        await page.waitForURL(/\/contacts/, { timeout: 10_000 });
        await expect(page).toHaveURL(/\/contacts/);
    });

    test('navigating to Companies tab goes to /companies', async ({ page }) => {
        await gotoAuthenticated(page, '/');
        await page.getByRole('tab', { name: /companies/i }).click();
        await page.waitForURL(/\/companies/, { timeout: 10_000 });
        await expect(page).toHaveURL(/\/companies/);
    });

    test('navigating to Deals tab goes to /deals', async ({ page }) => {
        await gotoAuthenticated(page, '/');
        await page.getByRole('tab', { name: /deals/i }).click();
        await page.waitForURL(/\/deals/, { timeout: 10_000 });
        await expect(page).toHaveURL(/\/deals/);
    });

    test('dashboard content renders (widgets/stepper present)', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/');
        // The Dashboard either shows DashboardStepper (step 1 or 2) or the full
        // grid with Welcome, HotContacts, etc.  In all cases at least one element
        // renders inside #main-content once the data loads.
        // Wait up to 20s for any visible element inside the main content.
        const mainContent = page.locator('#main-content');
        await expect(mainContent).toBeVisible({ timeout: 20_000 });
        // Wait for dashboard data to load and render something (either stepper or widgets).
        // The Dashboard returns null while data is pending, so we need to wait
        // for a child element to appear.
        await expect(mainContent.locator('> *').first()).toBeVisible({
            timeout: 20_000,
        });
    });

    test('user menu is accessible in header', async ({ page }) => {
        await gotoAuthenticated(page, '/');
        // react-admin UserMenu renders an IconButton with aria-label="Profile"
        // (translated from ra.auth.user_menu via ra-language-english: user_menu: 'Profile')
        const userMenuButton = page.getByRole('button', { name: 'Profile' });
        await expect(userMenuButton).toBeVisible();
    });

    test('clicking user menu shows My info and Logout options', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/');
        // Open user menu via the Profile button
        await page.getByRole('button', { name: 'Profile' }).click();
        await expect(page.getByText(/my info/i)).toBeVisible();
        await expect(
            page.getByRole('menuitem', { name: /logout/i })
        ).toBeVisible();
    });
});
