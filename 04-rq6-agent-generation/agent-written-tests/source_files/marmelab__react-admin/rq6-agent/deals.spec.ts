/**
 * Deals module tests: kanban list, create modal, show modal, filters.
 * Auth is bypassed via localStorage injection.
 */
import { test, expect } from '@playwright/test';
import { gotoAuthenticated } from './helpers';

test.describe('Deals list (kanban)', () => {
    test('deals page loads', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        await page.waitForLoadState('networkidle');
        await expect(page).toHaveURL(/\/deals/);
    });

    test('shows kanban stage columns', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        // Wait for kanban columns to render – each column shows a stage label.
        // defaultDealStages includes "Opportunity", "Proposal Sent", etc.
        // The DealListContent renders Droppable containers with data-rbd-droppable-id.
        await expect(
            page.locator('[data-rbd-droppable-id]').first()
        ).toBeVisible({ timeout: 20_000 });
        // The kanban board shows the stage name text
        await expect(page.getByText('Opportunity')).toBeVisible();
    });

    test('shows "New Deal" create button', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        await page.waitForLoadState('networkidle');
        // The CreateButton is labeled "New Deal"
        const newDealBtn = page.getByRole('link', { name: /new deal/i });
        await expect(newDealBtn).toBeVisible({ timeout: 15_000 });
    });

    test('shows Filter button', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        // react-admin's FilterButton renders as "Add filter" (ra.action.add_filter)
        await expect(
            page.getByRole('button', { name: /add filter/i })
        ).toBeVisible({ timeout: 15_000 });
    });

    test('shows Export button', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        await page.waitForLoadState('networkidle');
        await expect(page.getByRole('button', { name: /export/i })).toBeVisible(
            { timeout: 15_000 }
        );
    });
});

test.describe('Deal create modal', () => {
    test('clicking New Deal opens a modal dialog', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        await page.waitForLoadState('networkidle');

        const newDealBtn = page.getByRole('link', { name: /new deal/i });
        await expect(newDealBtn).toBeVisible({ timeout: 15_000 });
        await newDealBtn.click();

        // A Dialog should appear
        await expect(
            page.getByRole('dialog', { name: /create a new deal/i })
        ).toBeVisible({ timeout: 10_000 });
    });

    test('deal create modal has Deal name field', async ({ page }) => {
        await gotoAuthenticated(page, '/deals/create');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('textbox', { name: /deal name/i })
        ).toBeVisible({ timeout: 10_000 });
    });

    test('deal create modal has Amount field', async ({ page }) => {
        await gotoAuthenticated(page, '/deals/create');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('spinbutton', { name: /amount/i })
        ).toBeVisible({ timeout: 10_000 });
    });

    test('deal create modal has Stage field', async ({ page }) => {
        await gotoAuthenticated(page, '/deals/create');
        await page.waitForLoadState('networkidle');
        await expect(
            page.getByRole('combobox', { name: /stage/i })
        ).toBeVisible({ timeout: 10_000 });
    });

    test('can create a deal via the modal', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        await page.waitForLoadState('networkidle');

        const newDealBtn = page.getByRole('link', { name: /new deal/i });
        await expect(newDealBtn).toBeVisible({ timeout: 15_000 });
        await newDealBtn.click();

        const dialog = page.getByRole('dialog');
        await expect(dialog).toBeVisible({ timeout: 10_000 });

        const ts = Date.now();
        const dealName = `TestDeal${ts}`;

        // Fill deal name
        await dialog
            .getByRole('textbox', { name: /deal name/i })
            .fill(dealName);

        // Company is required – pick first available option from autocomplete
        const companyInput = dialog.getByRole('combobox', {
            name: /company/i,
        });
        await companyInput.click();
        const firstOption = page.getByRole('option').first();
        await expect(firstOption).toBeVisible({ timeout: 5_000 });
        await firstOption.click();

        // Expected closing date has a default value, so we don't need to fill it.
        // Save the deal
        await dialog.getByRole('button', { name: /save/i }).click();

        // Modal should close and we return to /deals
        await page.waitForURL(/\/deals$/, { timeout: 15_000 });
    });
});

test.describe('Deal show', () => {
    test('clicking a deal card opens show dialog', async ({ page }) => {
        await gotoAuthenticated(page, '/deals');
        // Wait for the kanban board to render (DealCards use @hello-pangea/dnd
        // Draggable which adds data-rbd-draggable-id to each card's wrapper Box)
        const firstCard = page.locator('[data-rbd-draggable-id]').first();
        await expect(firstCard).toBeVisible({ timeout: 20_000 });
        await firstCard.click();

        // After clicking a deal card, DealList renders DealShow with open=true
        // which is a Dialog rendered at the /deals/:id/show URL
        await page.waitForURL(/\/deals\/\d+\/show/, { timeout: 15_000 });
        // The deal show dialog should be visible
        await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 });
    });
});
