/**
 * Companies module tests: list, create, show, edit.
 * Auth is bypassed via localStorage injection.
 */
import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers';

test.describe('Companies list', () => {
    test('companies list page loads', async ({ page }) => {
        await gotoAuthenticated(page, '/companies');
        await page.waitForLoadState('networkidle');
        await expect(page).toHaveURL(/\/companies/);
    });

    test('shows companies in a grid', async ({ page }) => {
        await gotoAuthenticated(page, '/companies');
        // CompanyList renders CompanyCard items; each card is wrapped in a
        // react-admin Link (<a>) pointing to the company show page.
        // The grid is inside #main-content.
        const companyCardLinks = page
            .locator('#main-content')
            .getByRole('link')
            .first();
        await expect(companyCardLinks).toBeVisible({ timeout: 20_000 });
    });

    test('list toolbar has a Create button', async ({ page }) => {
        await gotoAuthenticated(page, '/companies');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('link', { name: /new company/i })
        ).toBeVisible();
    });

    test('list toolbar has an Export button', async ({ page }) => {
        await gotoAuthenticated(page, '/companies');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('button', { name: /export/i })
        ).toBeVisible();
    });
});

test.describe('Company create', () => {
    test('create company form renders name field', async ({ page }) => {
        await gotoAuthenticated(page, '/companies/create');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('textbox', { name: /name/i }).first()
        ).toBeVisible();
    });

    test('create company form renders Contact section', async ({ page }) => {
        await gotoAuthenticated(page, '/companies/create');
        await page.waitForLoadState('networkidle');
        await expect(page.getByText('Contact')).toBeVisible();
        await expect(
            page.getByRole('textbox', { name: /website/i })
        ).toBeVisible();
    });

    test('create company form renders Address section', async ({ page }) => {
        await gotoAuthenticated(page, '/companies/create');
        await page.waitForLoadState('networkidle');
        await expect(page.getByText('Address')).toBeVisible();
        await expect(
            page.getByRole('textbox', { name: /address/i })
        ).toBeVisible();
    });

    test('create company form renders Account manager section', async ({
        page,
    }) => {
        await gotoAuthenticated(page, '/companies/create');
        await page.waitForLoadState('networkidle');
        await expect(page.getByText(/account manager/i).first()).toBeVisible();
    });

    test('can create a company and redirect to show page', async ({ page }) => {
        await gotoAuthenticated(page, '/companies/create');
        await page.waitForLoadState('networkidle');

        const ts = Date.now();
        const companyName = `TestCo${ts}`;

        await page
            .getByRole('textbox', { name: /name/i })
            .first()
            .fill(companyName);

        // Account manager (sales_id) is required
        const accountManagerSelect = page.getByRole('combobox', {
            name: /account manager/i,
        });
        await expect(accountManagerSelect).toBeVisible({ timeout: 10_000 });
        await accountManagerSelect.click();
        const firstOption = page.getByRole('option').first();
        await expect(firstOption).toBeVisible({ timeout: 5_000 });
        await firstOption.click();

        await page.getByRole('button', { name: /save/i }).click();

        // After save, redirect to show page
        await page.waitForURL(/\/companies\/\d+\/show/, { timeout: 15_000 });
        await expect(page.getByText(companyName)).toBeVisible();
    });
});

test.describe('Company show', () => {
    test('company show page displays company details', async ({ page }) => {
        await gotoAuthenticated(page, '/companies');
        await page.waitForLoadState('networkidle');

        // Click the first company card / link
        const firstCompanyLink = page
            .locator('#main-content')
            .getByRole('link')
            .first();
        await expect(firstCompanyLink).toBeVisible({ timeout: 15_000 });
        await firstCompanyLink.click();

        // Should navigate to either show or edit page
        await page.waitForURL(/\/companies\/\d+/, { timeout: 15_000 });
        await expect(page).toHaveURL(/\/companies\/\d+/);
    });
});
