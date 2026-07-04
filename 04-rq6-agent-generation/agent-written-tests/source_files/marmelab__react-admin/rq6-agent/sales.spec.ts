/**
 * Sales (Users) module tests: list, create form.
 * Auth is bypassed via localStorage injection (admin role required).
 */
import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers';

test.describe('Sales list', () => {
    test('sales list page loads via /sales', async ({ page }) => {
        await gotoAuthenticated(page, '/sales');
        await page.waitForLoadState('networkidle');
        await expect(page).toHaveURL(/\/sales/);
    });

    test('shows sales persons in a table', async ({ page }) => {
        await gotoAuthenticated(page, '/sales');
        await page.waitForLoadState('networkidle');
        // react-admin DataTable renders rows as <tr> elements
        const rows = page.locator('tbody tr');
        await expect(rows.first()).toBeVisible({ timeout: 15_000 });
    });

    test('list has a Create button for new user', async ({ page }) => {
        await gotoAuthenticated(page, '/sales');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('link', { name: /new user/i })
        ).toBeVisible();
    });

    test('list has an Export button', async ({ page }) => {
        await gotoAuthenticated(page, '/sales');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('button', { name: /export/i })
        ).toBeVisible();
    });

    test('list shows Name column header', async ({ page }) => {
        await gotoAuthenticated(page, '/sales');
        await page.waitForLoadState('networkidle');
        // The list uses a DataTable with a Name column
        await expect(
            page.getByRole('columnheader', { name: /name/i })
        ).toBeVisible({
            timeout: 10_000,
        });
    });

    test('list shows Email column header', async ({ page }) => {
        await gotoAuthenticated(page, '/sales');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('columnheader', { name: /email/i })
        ).toBeVisible({ timeout: 10_000 });
    });
});

test.describe('Sales create', () => {
    test('create sales person page renders required fields', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/sales/create');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('textbox', { name: /first.name/i })
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole('textbox', { name: /last.name/i })
        ).toBeVisible();
        await expect(
            page.getByRole('textbox', { name: /email/i })
        ).toBeVisible();
    });

    test('create form has Administrator and Disabled toggles', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/sales/create');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('checkbox', { name: /administrator/i })
        ).toBeVisible({ timeout: 10_000 });
        await expect(
            page.getByRole('checkbox', { name: /disabled/i })
        ).toBeVisible();
    });

    test('can create a sales person and redirect to sales list', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/sales/create');

        const ts = Date.now();
        await page
            .getByRole('textbox', { name: /first.name/i })
            .fill(`First${ts}`);
        await page
            .getByRole('textbox', { name: /last.name/i })
            .fill(`Last${ts}`);
        await page
            .getByRole('textbox', { name: /email/i })
            .fill(`test${ts}@example.com`);

        await page.getByRole('button', { name: /save/i }).click();

        // SalesCreate calls redirect('/sales') on success
        await page.waitForURL(/\/sales$/, { timeout: 15_000 });
        await expect(page).toHaveURL(/\/sales/);
    });
});
